"""账号注册、密码和设备会话的业务规则。"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import urlsplit
from uuid import uuid4
import asyncio
import os
import time

from anyio.to_thread import run_sync
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from argon2.low_level import Type

from models.auth import Account, AuthProblem
from services.ai_client import AIServiceError
from storage.accounts import AccountsDatabase, take_ai_usage, take_auth_limit

DAY = 86_400
SESSION_MAX_AGE = 30 * DAY
SESSION_IDLE = 7 * DAY
LIMIT_WINDOWS = {"login_ip": 60, "login_username": 900, "register_ip": 3600, "register_site": 3600}


def _digest(token):
    return sha256(token.encode()).hexdigest()


def _invalid_login():
    return AuthProblem(401, "invalid_login", "用户名或密码不正确。")


def _site_origin(production):
    origin = os.getenv("SITE_ORIGIN", "" if production else "http://127.0.0.1:5173").rstrip("/")
    parts = urlsplit(origin)
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.path or parts.query or parts.fragment):
        raise ValueError("SITE_ORIGIN 必须是站点的公开来源，例如 https://video.example.com")
    if production and parts.scheme != "https":
        raise ValueError("生产 SITE_ORIGIN 必须使用 HTTPS")
    return origin


class Accounts:
    def __init__(self, directory):
        self.production = os.getenv("APP_ENV") == "production"
        self.origin = _site_origin(self.production)
        self.cookie_name = "__Host-magical-session" if self.production else "magical-session"
        self.database = AccountsDatabase(directory)
        self.hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)
        self.dummy_hash = self.hasher.hash(token_urlsafe(32))
        self.password_slots = asyncio.Semaphore(2)
        self.ai_slots = asyncio.Semaphore(2)
        self.account_ai_limit = self._usage_limit("AUTH_AI_ACCOUNT_DAILY", 30)
        self.site_ai_limit = self._usage_limit("AUTH_AI_SITE_DAILY", 300)
        self.last_cleanup = 0

    def _usage_limit(self, key, default):
        value = int(os.getenv(key, "" if self.production else str(default)))
        if value < 1:
            raise ValueError(f"{key} 必须是正整数")
        return value

    async def register(self, username, password, ip, previous=None):
        if not 15 <= len(password) <= 128 or not password.strip():
            raise AuthProblem(422, "password_length", "密码需为 15 至 128 个字符。")
        now = int(time.time())
        with self.database.transaction(write=True) as connection:
            self._cleanup(connection, now)
            permitted = (
                take_auth_limit(connection, "register_ip", _digest(ip), now // LIMIT_WINDOWS["register_ip"], 30)
                and take_auth_limit(connection, "register_site", "", now // LIMIT_WINDOWS["register_site"], 100)
            )
        if not permitted:
            raise AuthProblem(429, "auth_rate_limit", "注册尝试过多，请稍后再试。")

        async with self.password_slots:
            password_hash = await run_sync(self.hasher.hash, password)
        user = Account(uuid4().hex, username.casefold())
        with self.database.transaction(write=True) as connection:
            inserted = connection.execute(
                "INSERT INTO accounts (id, username, password_hash) VALUES (?, ?, ?) ON CONFLICT(username) DO NOTHING",
                (user.id, user.username, password_hash),
            ).rowcount
            if not inserted:
                raise AuthProblem(409, "username_taken", "这个用户名已被使用，请换一个。")
            token = self._start_session(connection, user.id, previous)
        return user, token

    async def login(self, username, password, ip, previous=None):
        username = username.casefold()
        now = int(time.time())
        with self.database.transaction(write=True) as connection:
            self._cleanup(connection, now)
            permitted = (
                take_auth_limit(connection, "login_ip", _digest(ip), now // LIMIT_WINDOWS["login_ip"], 20)
                and take_auth_limit(connection, "login_username", _digest(username), now // LIMIT_WINDOWS["login_username"], 10)
            )
            row = connection.execute(
                "SELECT id, password_hash FROM accounts WHERE username=?", (username,),
            ).fetchone() if permitted else None
        if not permitted:
            raise AuthProblem(429, "auth_rate_limit", "登录尝试过多，请稍后再试。")
        if len(password) > 128:
            raise _invalid_login()

        password_hash = row["password_hash"] if row else self.dummy_hash
        try:
            async with self.password_slots:
                await run_sync(self.hasher.verify, password_hash, password)
        except VerificationError:
            raise _invalid_login() from None
        if not row:
            raise _invalid_login()

        with self.database.transaction(write=True) as connection:
            # 确认耗时的密码校验期间账号凭据未变更。
            current = connection.execute(
                "SELECT username, password_hash, is_admin FROM accounts WHERE id=?", (row["id"],),
            ).fetchone()
            if not current or current["password_hash"] != password_hash:
                raise _invalid_login()
            token = self._start_session(connection, row["id"], previous)
        return Account(row["id"], current["username"], bool(current["is_admin"])), token

    @staticmethod
    def _start_session(connection, account_id, previous):
        token = token_urlsafe(32)
        now = int(time.time())
        if previous:
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (_digest(previous),))
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (_digest(token), account_id, now, now + SESSION_MAX_AGE),
        )
        return token

    def authenticate(self, token, *, touch=True):
        if not token or len(token) != 43:
            return None
        digest = _digest(token)
        now = int(time.time())
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT a.id, a.username, a.is_admin, s.last_seen FROM sessions s JOIN accounts a ON a.id=s.account_id
                   WHERE s.token_hash=? AND s.expires_at>? AND s.last_seen>?""",
                (digest, now, now - SESSION_IDLE),
            ).fetchone()
        if not row:
            return None
        if touch and now - row["last_seen"] >= 60:
            with self.database.transaction(write=True) as connection:
                connection.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (now, digest))
        return Account(row["id"], row["username"], bool(row["is_admin"]))

    def logout(self, token):
        if token and len(token) == 43:
            with self.database.transaction(write=True) as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash=?", (_digest(token),))

    def _cleanup(self, connection, now):
        if self.last_cleanup > now - 3600:
            return
        connection.execute("DELETE FROM sessions WHERE expires_at<=? OR last_seen<=?", (now, now - SESSION_IDLE))
        connection.executemany(
            "DELETE FROM auth_limits WHERE bucket=? AND window<?",
            [(bucket, now // seconds) for bucket, seconds in LIMIT_WINDOWS.items()],
        )
        connection.execute("DELETE FROM ai_usage WHERE day<?", (now // DAY - 30,))
        self.last_cleanup = now

    @asynccontextmanager
    async def model_request(self, account_id):
        async with self.ai_slots:
            day = int(time.time()) // DAY
            with self.database.transaction(write=True) as connection:
                if not (take_ai_usage(connection, day, account_id, self.account_ai_limit)
                        and take_ai_usage(connection, day, "site", self.site_ai_limit)):
                    reset = datetime.fromtimestamp((day + 1) * DAY, timezone(timedelta(hours=8)))
                    raise AIServiceError(429, f"今日 AI 额度已用完，香港时间 {reset:%m-%d %H:%M} 恢复。",
                                         code="ai_quota")
            yield
