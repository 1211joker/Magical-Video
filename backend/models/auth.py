"""站内账号和会话的请求契约。"""

from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, SecretStr, StringConstraints


@dataclass(frozen=True)
class Account:
    id: str
    username: str
    is_admin: bool = False


class AuthProblem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code


class LoginRequest(BaseModel):
    # 旧账号的登录名可能仍是原邮箱地址。
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    password: SecretStr


class RegisterRequest(LoginRequest):
    username: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"),
    ]
