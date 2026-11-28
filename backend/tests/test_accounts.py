import asyncio
from contextlib import closing, ExitStack
from dataclasses import replace
import json
from pathlib import Path
from shutil import copyfile
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from auth_support import DEFAULT_USERNAME, PASSWORD, account_client, login, register
from main import app
from maintenance import backup, import_library, restore
from services.ai_client import PROVIDERS
from services.analysis_service import analyze_subtitles
from services.auth import SESSION_IDLE
from services.ytdlp_service import PreparedVideo
from test_study import VIDEOS, fake_analysis, fake_answer, fake_open, fake_wiki

PREFIX = "/api/study"
SECOND_USERNAME = "bob"


def submit_analysis(client, url=VIDEOS[0], *, save=True, job_id=None):
    response = client.post(PREFIX + "/analysis", json={"url": url, "request_id": job_id or uuid4().hex, "save": save})
    assert response.status_code == 202, response.text
    return response.json()["id"]


def wait_job(client, job_id, state="done"):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = client.get(f"{PREFIX}/tasks/{job_id}")
        assert response.status_code == 200, response.text
        job = response.json()
        if job["state"] == state:
            return job
        assert job["state"] in {"queued", "running"}, job
        time.sleep(0.02)
    raise AssertionError(f"任务未进入 {state}")


class AccountTests(unittest.TestCase):
    def test_registration_and_login_issue_separate_secure_device_sessions(self):
        with account_client(signed_in=False, origin="https://testserver", APP_ENV="production") as client:
            payload = {"username": DEFAULT_USERNAME, "password": PASSWORD}
            self.assertEqual(client.post("/api/auth/login", json=payload).status_code, 401)
            response = client.post("/api/auth/register", json=payload)
            self.assertEqual(response.status_code, 201, response.text)
            header = response.headers["Set-Cookie"]
            for flag in ("__Host-magical-session=", "Path=/", "Secure", "HttpOnly", "SameSite=lax", "Max-Age=2592000"):
                self.assertIn(flag, header)
            self.assertNotIn("Domain=", header)
            cookie = "__Host-magical-session"
            desktop = client.cookies.get(cookie)
            self.assertEqual(client.get("/api/auth/session").json(), response.json())
            course = client.post(PREFIX + "/courses", json={"title": "跨设备的课程"}).json()["id"]
            client.cookies.clear()
            self.assertEqual(login(client, DEFAULT_USERNAME.upper()), response.json())
            self.assertEqual(client.get(f"{PREFIX}/courses/{course}").json()["title"], "跨设备的课程")
            mobile = client.cookies.get(cookie)
            self.assertNotEqual(desktop, mobile)
            self.assertEqual(client.post("/api/auth/logout").status_code, 204)
            self.assertEqual(client.get("/api/auth/session", headers={"Cookie": f"{cookie}={mobile}"}).status_code, 401)
            self.assertEqual(client.get("/api/auth/session", headers={"Cookie": f"{cookie}={desktop}"}).status_code, 200)
            with app.state.accounts.database.transaction() as connection:
                password_hash = connection.execute("SELECT password_hash FROM accounts").fetchone()[0]
                session_hash = connection.execute("SELECT token_hash FROM sessions").fetchone()[0]
                self.assertTrue(password_hash.startswith("$argon2id$"))
                self.assertNotEqual(session_hash, desktop)

    def test_invalid_and_duplicate_usernames_cannot_overwrite_credentials(self):
        with account_client(signed_in=False) as client:
            for username in ("ab", "a" * 33, "with space", "-starts-with-symbol", "alice@example.com"):
                response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
                self.assertEqual((response.status_code, response.json()["code"]), (422, "invalid_request"))
            for password in ("short", " " * 15, "x" * 129):
                response = client.post("/api/auth/register", json={"username": DEFAULT_USERNAME, "password": password})
                self.assertEqual((response.status_code, response.json()["code"]), (422, "password_length"))
            account = register(client, " Alice ")
            self.assertEqual(account["username"], DEFAULT_USERNAME)
            another_password = "a different fixture password"
            duplicate = {"username": "ALICE", "password": another_password}
            response = client.post("/api/auth/register", json=duplicate)
            self.assertEqual((response.status_code, response.json()["code"]), (409, "username_taken"))
            self.assertEqual(client.post("/api/auth/login", json=duplicate).status_code, 401)
            self.assertEqual(client.get("/api/auth/session").json(), account)
            self.assertEqual(login(client), account)

    def test_origin_and_account_required_at_all_business_entry_points(self):
        with account_client(signed_in=False) as client:
            for method, path in [
                ("GET", "/api/study/library"), ("POST", "/api/study/session"), ("GET", "/api/ai/providers"),
                ("POST", "/api/parse"), ("POST", "/api/subtitles"), ("POST", "/api/ask"),
                ("POST", "/api/analyze-stream"), ("POST", "/api/download"), ("GET", "/api/thumbnail"),
                ("GET", "/api/download/jobs/known-id/file"),
            ]:
                response = client.request(method, path)
                self.assertEqual((response.status_code, response.json()["code"]), (401, "auth_required"), path)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(client.get("/api/health").status_code, 200)
            account = register(client)
            target = PREFIX + "/courses"
            data = {"title": "我的课程"}
            self.assertEqual(client.post(target, json=data, headers={"Origin": "https://other.example.com"}).status_code, 403)
            self.assertEqual(client.post(target, json=data, headers={"Sec-Fetch-Site": "same-site"}).status_code, 403)
            self.assertEqual(client.post(target, json=data, headers={"X-Account-Id": uuid4().hex}).status_code, 401)
            self.assertEqual(client.post(target, json=data, headers={"X-Account-Id": account["id"]}).status_code, 201)
            del client.headers["Origin"]
            self.assertEqual(client.post(target, json=data).status_code, 403)
            self.assertEqual(client.post(target, json=data, headers={"Referer": "http://testserver/"}).status_code, 201)

    def test_sessions_survive_restart_but_expire(self):
        with TemporaryDirectory() as root:
            with account_client(root) as client:
                session = client.cookies.get("magical-session")
                expected = client.get("/api/auth/session").json()
            with account_client(root, signed_in=False) as client:
                client.cookies.set("magical-session", session)
                self.assertEqual(client.get("/api/auth/session").json(), expected)
                db = app.state.accounts.database
                with db.transaction(write=True) as connection:
                    connection.execute("UPDATE sessions SET last_seen=?", (int(time.time()) - SESSION_IDLE,))
                self.assertEqual(client.get("/api/auth/session").status_code, 401)
                login(client)
                with db.transaction(write=True) as connection:
                    connection.execute("UPDATE sessions SET expires_at=?", (int(time.time()) - 1,))
                self.assertEqual(client.get("/api/auth/session").status_code, 401)

    def test_registration_is_rate_limited(self):
        with account_client() as client:
            with app.state.accounts.database.transaction(write=True) as connection:
                connection.execute("UPDATE auth_limits SET count=30 WHERE bucket='register_ip'")
            response = client.post("/api/auth/register", json={"username": SECOND_USERNAME, "password": PASSWORD})
            self.assertEqual((response.status_code, response.json()["code"]), (429, "auth_rate_limit"))
            self.assertEqual(client.get("/api/auth/session").json()["username"], DEFAULT_USERNAME)

    def test_registration_cannot_assign_admin_role(self):
        with account_client(signed_in=False) as client:
            payload = {"username": "admin", "password": PASSWORD, "is_admin": True}
            response = client.post("/api/auth/register", json=payload)
            self.assertEqual(response.status_code, 201)
            self.assertFalse(response.json()["is_admin"])
            database = app.state.accounts.database
            self.assertFalse(database.promote_admin("missing"))
            self.assertTrue(database.promote_admin(" ADMIN "))
            self.assertTrue(client.get("/api/auth/session").json()["is_admin"])
            self.assertTrue(login(client, "admin")["is_admin"])
            self.assertFalse(register(client)["is_admin"])

    def test_legacy_accounts_and_backups_keep_passwords_and_library_ids(self):
        for version in (1, 2):
            legacy_name = "legacy@example.com" if version == 1 else DEFAULT_USERNAME
            with self.subTest(version=version), TemporaryDirectory() as directory:
                root = Path(directory)
                legacy = root / "legacy"
                with account_client(legacy) as client:
                    user = client.get("/api/auth/session").json()
                    token = client.cookies.get("magical-session")
                    course = client.post(PREFIX + "/courses", json={"title": "升级前的课程"}).json()["id"]
                    database = app.state.accounts.database
                with database.transaction(write=True) as connection:
                    connection.execute("ALTER TABLE accounts DROP COLUMN is_admin")
                    if version == 1:
                        connection.execute("UPDATE accounts SET username=?", (legacy_name,))
                        connection.execute("ALTER TABLE accounts RENAME COLUMN username TO email")
                        connection.execute(
                            "CREATE TABLE email_actions (token_hash TEXT PRIMARY KEY, purpose TEXT, email TEXT, expires_at INTEGER)"
                        )
                    connection.execute(f"PRAGMA user_version={version}")
                snapshot = root / "snapshot"
                backup(legacy, snapshot)
                for path in snapshot.rglob("*.sqlite3"):
                    with closing(sqlite3.connect(path)) as archive:
                        self.assertEqual(archive.execute("PRAGMA journal_mode").fetchone()[0], "delete")
                        archive.execute("PRAGMA journal_mode=WAL")
                directories = [snapshot, *(path for path in snapshot.rglob("*") if path.is_dir())]
                try:
                    for path in directories:
                        path.chmod(0o500)
                    restore(snapshot, root / "restored")
                finally:
                    for path in directories:
                        path.chmod(0o700)
                expected = {"id": user["id"], "username": legacy_name, "is_admin": False}
                with account_client(root / "restored", signed_in=False) as client:
                    client.cookies.set("magical-session", token)
                    self.assertEqual(client.get("/api/auth/session").status_code, 401)
                    self.assertEqual(login(client, legacy_name.upper()), expected)
                    self.assertEqual(client.get(f"{PREFIX}/courses/{course}").json()["title"], "升级前的课程")
                with account_client(legacy, signed_in=False) as client:
                    client.cookies.set("magical-session", token)
                    self.assertEqual(client.get("/api/auth/session").json(), expected)
                    self.assertEqual(client.get(f"{PREFIX}/courses/{course}").status_code, 200)


class AccountLibraryTests(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(ExitStack())
        primary = replace(PROVIDERS["deepseek"], api_key="fixture-key")
        stack.enter_context(patch.dict(PROVIDERS, {"deepseek": primary}))
        self.open = stack.enter_context(patch("services.study.open_video", side_effect=fake_open))
        self.analysis = stack.enter_context(patch("services.study.analyze_subtitles", side_effect=fake_analysis))
        self.wiki = stack.enter_context(patch("services.study_ai.generate_wiki", side_effect=fake_wiki))
        self.answer = stack.enter_context(patch("services.study_ai.generate_answer", side_effect=fake_answer))

    def test_cross_account_ids_are_hidden_and_model_context_is_local(self):
        with TemporaryDirectory() as directory, account_client() as client:
            first_job = submit_analysis(client)
            archive = wait_job(client, first_job)["result"]
            course = client.post(PREFIX + "/courses", json={"title": "第一门课"}).json()["id"]
            wiki_job = client.put(f"{PREFIX}/courses/{course}/videos/{archive['id']}").json()["id"]
            wait_job(client, wiki_job)
            wiki_page = client.get(f"{PREFIX}/courses/{course}").json()["wiki_pages"][0]["id"]
            conversation = client.post(PREFIX + "/conversations", json={"scope": "course", "scope_id": course}).json()["id"]
            temp_job = submit_analysis(client, save=False)
            wait_job(client, temp_job)
            file = Path(directory) / "sample.mp4"
            file.write_bytes(b"fixture")
            with patch("services.download_service.prepare_download", return_value=PreparedVideo(file)):
                dl = client.post("/api/download/jobs", json={"url": VIDEOS[0]}).json()["job_id"]
            register(client, SECOND_USERNAME)
            self.assertEqual(client.get(PREFIX + "/library").json()["videos"], [])
            self.assertEqual(client.get(PREFIX + "/conversations").json(), [])
            for method, path, options in [
                ("GET", f"{PREFIX}/videos/{archive['id']}", {}),
                ("GET", f"{PREFIX}/courses/{course}", {}),
                ("GET", f"{PREFIX}/wiki/{wiki_page}", {}),
                ("GET", f"{PREFIX}/conversations/{conversation}", {}),
                ("GET", f"{PREFIX}/tasks/{temp_job}", {}),
                ("DELETE", f"{PREFIX}/analysis/{temp_job}", {}),
                ("PUT", f"{PREFIX}/analysis/{temp_job}/archive", {"json": {}}),
                ("POST", f"{PREFIX}/tasks/{temp_job}/retry", {"json": {}}),
                ("DELETE", f"{PREFIX}/tasks/{wiki_job}", {}),
                ("GET", f"/api/download/jobs/{dl}", {}),
                ("GET", f"/api/download/jobs/{dl}/file", {}),
                ("DELETE", f"/api/download/jobs/{dl}", {}),
            ]:
                blocked = client.request(method, path, **options)
                self.assertEqual(blocked.status_code, 404, (path, blocked.text))
            other = wait_job(client, submit_analysis(client, job_id=first_job))["result"]
            self.assertNotEqual(archive["id"], other["id"])
            mine = client.post(PREFIX + "/conversations", json={"scope": "library"}).json()["id"]
            question = client.post(f"{PREFIX}/conversations/{mine}/questions", json={
                "question": "梯度下降如何更新权重？", "request_id": uuid4().hex,
            }).json()["id"]
            wait_job(client, question)
            evidence = self.answer.await_args.args[1]
            self.assertEqual({item["video_id"] for item in evidence}, {other["id"]})
            login(client)
            self.assertEqual(client.get(f"/api/download/jobs/{dl}/file").content, b"fixture")
            self.assertEqual(client.put(f"{PREFIX}/analysis/{temp_job}/archive", json={}).status_code, 200)

    def test_pending_accounts_take_turns_on_the_shared_worker(self):
        started = Event()
        release = Event()
        order = []

        async def ordered(url, **kwargs):
            order.append(url)
            if url == VIDEOS[0]:
                started.set()
                while not release.is_set():
                    await asyncio.sleep(0.01)
            return await fake_open(url, **kwargs)

        self.open.side_effect = ordered
        with account_client() as client:
            first = submit_analysis(client, VIDEOS[0])
            self.assertTrue(started.wait(3))
            second = submit_analysis(client, VIDEOS[1])
            register(client, SECOND_USERNAME)
            third = submit_analysis(client, VIDEOS[2])
            release.set()
            wait_job(client, third)
            login(client)
            wait_job(client, first)
            wait_job(client, second)
            self.assertEqual(order, [VIDEOS[0], VIDEOS[2], VIDEOS[1]])

    def test_model_calls_instant_and_background_share_account_and_site_limits(self):
        self.analysis.side_effect = analyze_subtitles
        upstream = []

        def respond(request):
            upstream.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"overview": "分析资料"})}}]})

        transport = httpx.MockTransport(respond)
        make = httpx.AsyncClient
        with account_client(AUTH_AI_ACCOUNT_DAILY="1", AUTH_AI_SITE_DAILY="1") as client, \
                patch("services.ai_client.httpx.AsyncClient", side_effect=lambda **kwargs: make(transport=transport, **kwargs)):
            wait_job(client, submit_analysis(client))
            body = {"question": "解释梯度", "subtitle_text": "梯度梯度"}
            blocked = client.post("/api/ask", json=body)
            self.assertEqual((blocked.status_code, blocked.json()["code"]), (429, "ai_quota"))
            self.assertIn("恢复", blocked.json()["detail"])
            self.assertEqual(len(client.get(PREFIX + "/library").json()["videos"]), 1)
            register(client, SECOND_USERNAME)
            failed = wait_job(client, submit_analysis(client, VIDEOS[1]), "failed")
            self.assertEqual(failed["code"], "ai_quota")
            self.assertEqual(len(upstream), 1)
            with app.state.accounts.database.transaction() as connection:
                usage = connection.execute("SELECT count FROM ai_usage").fetchall()
                self.assertEqual([row["count"] for row in usage], [1, 1])

    def test_upstream_retry_cannot_exceed_daily_limit(self):
        upstream = []

        def refuse(request):
            upstream.append(request)
            return httpx.Response(503)

        async def retry_without_delay(_seconds):
            pass

        transport = httpx.MockTransport(refuse)
        make = httpx.AsyncClient
        with account_client(AUTH_AI_ACCOUNT_DAILY="1") as client, \
                patch("services.ai_client.httpx.AsyncClient", side_effect=lambda **kwargs: make(transport=transport, **kwargs)), \
                patch("services.ai_client._post.retry.sleep", new=retry_without_delay):
            response = client.post("/api/ask", json={"question": "解释梯度", "subtitle_text": "梯度梯度"})
        self.assertEqual((response.status_code, response.json()["code"]), (429, "ai_quota"))
        self.assertEqual(len(upstream), 1)

    def test_import_preserves_archive_and_restore_keeps_accounts_without_old_sessions(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy.sqlite3"
            legacy_wal = root / "legacy.sqlite3-wal"
            working_copy = root / "legacy-working.sqlite3"
            with account_client(root / "source") as client:
                account = client.get("/api/auth/session").json()
                video = wait_job(client, submit_analysis(client))["result"]
                course = client.post(PREFIX + "/courses", json={"title": "旧课程"}).json()["id"]
                wiki_job = client.put(f"{PREFIX}/courses/{course}/videos/{video['id']}").json()["id"]
                wait_job(client, wiki_job)
                conversation = client.post(PREFIX + "/conversations", json={"scope": "course", "scope_id": course}).json()["id"]
                question = client.post(f"{PREFIX}/conversations/{conversation}/questions", json={
                    "question": "梯度下降如何更新权重？", "request_id": uuid4().hex,
                }).json()["id"]
                wait_job(client, question)
                turns = client.get(f"{PREFIX}/conversations/{conversation}").json()["turns"]
                self.assertTrue(turns[0]["citations"])
                source_file = root / "source" / "users" / account["id"] / "library.sqlite3"
            with closing(sqlite3.connect(source_file)) as source, closing(sqlite3.connect(working_copy)) as destination:
                source.backup(destination)
                destination.execute("PRAGMA journal_mode=WAL")
                destination.execute("PRAGMA wal_autocheckpoint=0")
                destination.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                destination.execute("UPDATE jobs SET state='running', phase='ai' WHERE id=?", (wiki_job,))
                destination.commit()
                copyfile(working_copy, legacy)
                copyfile(root / "legacy-working.sqlite3-wal", legacy_wal)
            before = legacy.read_bytes(), legacy_wal.read_bytes()
            with account_client(root / "target") as client:
                old_session = client.cookies.get("magical-session")
                self.assertEqual(client.get(PREFIX + "/library").json()["videos"], [])
            import_library(root / "target", legacy, DEFAULT_USERNAME)
            self.assertEqual((legacy.read_bytes(), legacy_wal.read_bytes()), before)
            with self.assertRaisesRegex(ValueError, "已有资料"):
                import_library(root / "target", legacy, DEFAULT_USERNAME)
            backup(root / "target", root / "snapshot")
            restore(root / "snapshot", root / "restored")
            with account_client(root / "restored", signed_in=False) as client:
                client.cookies.set("magical-session", old_session)
                self.assertEqual(client.get("/api/auth/session").status_code, 401)
                client.cookies.clear()
                login(client)
                data = client.get(f"{PREFIX}/courses/{course}").json()
                self.assertEqual([item["id"] for item in data["videos"]], [video["id"]])
                self.assertTrue(data["wiki_pages"])
                self.assertEqual(client.get(f"{PREFIX}/conversations/{conversation}").json()["turns"], turns)
                self.assertEqual(client.get(f"{PREFIX}/tasks/{wiki_job}").json()["state"], "cancelled")
