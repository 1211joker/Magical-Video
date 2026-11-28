"""站内注册、登录和设备会话的 HTTP 接口。"""

from fastapi import APIRouter, Request, Response

from models.auth import Account, LoginRequest, RegisterRequest
from services.auth import SESSION_MAX_AGE

router = APIRouter(prefix="/api/auth", tags=["auth"])

PUBLIC_AUTH = {("POST", "/api/auth/register"), ("POST", "/api/auth/login")}


def _set_session_cookie(response, accounts, token):
    response.set_cookie(accounts.cookie_name, token, max_age=SESSION_MAX_AGE, path="/",
                        secure=accounts.production, httponly=True, samesite="lax")


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request, response: Response) -> Account:
    accounts = request.app.state.accounts
    user, token = await accounts.register(
        body.username, body.password.get_secret_value(), request.client.host, request.cookies.get(accounts.cookie_name),
    )
    _set_session_cookie(response, accounts, token)
    return user


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response) -> Account:
    accounts = request.app.state.accounts
    user, token = await accounts.login(
        body.username, body.password.get_secret_value(), request.client.host, request.cookies.get(accounts.cookie_name),
    )
    _set_session_cookie(response, accounts, token)
    return user


@router.get("/session")
async def session(request: Request) -> Account:
    return request.state.user


@router.post("/logout", status_code=204)
async def logout(request: Request):
    accounts = request.app.state.accounts
    accounts.logout(request.cookies.get(accounts.cookie_name))
    response = Response(status_code=204)
    response.delete_cookie(accounts.cookie_name, path="/", secure=accounts.production, httponly=True, samesite="lax")
    return response
