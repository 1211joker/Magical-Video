"""使用真实注册和 Cookie 访问受保护 API 的测试准备。"""

from contextlib import ExitStack, contextmanager
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

DEFAULT_USERNAME = "alice"
PASSWORD = "fixture password for account"


def register(client, username=DEFAULT_USERNAME):
    response = client.post("/api/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def login(client, username=DEFAULT_USERNAME, password=PASSWORD):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


@contextmanager
def account_client(directory=None, *, signed_in=True, origin="http://testserver", **options):
    with ExitStack() as stack:
        directory = directory or stack.enter_context(TemporaryDirectory())
        stack.enter_context(patch.dict(os.environ, {
            "APP_ENV": "development", "SITE_ORIGIN": origin, "STUDY_DATA_DIR": str(directory),
            "STUDY_SEMANTIC": "0", "STUDY_ENABLED": "1",
            "AUTH_AI_ACCOUNT_DAILY": "30", "AUTH_AI_SITE_DAILY": "300", **options,
        }))
        with TestClient(app, base_url=origin, headers={"Origin": origin}) as client:
            if signed_in:
                if app.state.accounts.database.id_for_username(DEFAULT_USERNAME):
                    login(client)
                else:
                    register(client)
            yield client
