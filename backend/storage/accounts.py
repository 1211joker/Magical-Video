"""账号、会话和使用量的 SQLite 存储。"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

ACCOUNT_SCHEMA_VERSION = 3
ACCOUNT_MIGRATION_VERSIONS = (1, 2)
ACCOUNT_SUPPORTED_VERSIONS = (*ACCOUNT_MIGRATION_VERSIONS, ACCOUNT_SCHEMA_VERSION)
ADMIN_COLUMN = "is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1))"
SCHEMA = (
    f"""CREATE TABLE accounts (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        {ADMIN_COLUMN}
    )""",
    """CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY,
        account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        last_seen INTEGER NOT NULL,
        expires_at INTEGER NOT NULL
    )""",
    "CREATE INDEX session_account ON sessions(account_id)",
    """CREATE TABLE auth_limits (
        bucket TEXT NOT NULL,
        subject TEXT NOT NULL,
        window INTEGER NOT NULL,
        count INTEGER NOT NULL,
        PRIMARY KEY (bucket, subject, window)
    )""",
    """CREATE TABLE ai_usage (
        day INTEGER NOT NULL,
        subject TEXT NOT NULL,
        count INTEGER NOT NULL,
        PRIMARY KEY (day, subject)
    )""",
)


class AccountsDatabase:
    def __init__(self, directory: Path):
        self.path = directory / "accounts.sqlite3"

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.transaction() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                for statement in SCHEMA:
                    connection.execute(statement)
            elif version == 1:
                # 原邮箱地址成为旧账号的登录名，账号编号、密码和资料路径保持不变。
                connection.execute("ALTER TABLE accounts RENAME COLUMN email TO username")
                connection.execute("DROP TABLE IF EXISTS email_actions")
                connection.execute("UPDATE auth_limits SET bucket='login_username' WHERE bucket='login_email'")
                connection.execute("DELETE FROM auth_limits WHERE bucket IN ('email_ip', 'email_address', 'email_site')")
            elif version not in ACCOUNT_SUPPORTED_VERSIONS:
                raise RuntimeError("账号数据库版本不受当前程序支持")
            if version in ACCOUNT_MIGRATION_VERSIONS:
                connection.execute(f"ALTER TABLE accounts ADD COLUMN {ADMIN_COLUMN}")
            if version != ACCOUNT_SCHEMA_VERSION:
                connection.execute(f"PRAGMA user_version={ACCOUNT_SCHEMA_VERSION}")
        self.path.chmod(0o600)

    @contextmanager
    def transaction(self, *, write=False):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def ids(self):
        with self.transaction() as connection:
            return [row["id"] for row in connection.execute("SELECT id FROM accounts")]

    def id_for_username(self, username):
        if not self.path.is_file():
            return None
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id FROM accounts WHERE username=?", (username.strip().casefold(),),
            ).fetchone()
            return row["id"] if row else None

    def promote_admin(self, username):
        if not self.path.is_file():
            return False
        with self.transaction(write=True) as connection:
            return connection.execute(
                "UPDATE accounts SET is_admin=1 WHERE username=?", (username.strip().casefold(),),
            ).rowcount == 1


def take_auth_limit(connection, bucket, subject, window, limit):
    return connection.execute(
        """INSERT INTO auth_limits(bucket, subject, window, count) VALUES (?, ?, ?, 1)
           ON CONFLICT(bucket, subject, window) DO UPDATE SET count=count+1 WHERE count < ?""",
        (bucket, subject, window, limit),
    ).rowcount == 1


def take_ai_usage(connection, day, subject, limit):
    return connection.execute(
        """INSERT INTO ai_usage(day, subject, count) VALUES (?, ?, 1)
           ON CONFLICT(day, subject) DO UPDATE SET count=count+1 WHERE count < ?""",
        (day, subject, limit),
    ).rowcount == 1
