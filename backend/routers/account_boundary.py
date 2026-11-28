"""为应用 API 统一建立可信账号上下文。"""

from urllib.parse import urlsplit

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse

from routers.auth import PUBLIC_AUTH
from services.ai_client import using_account_ai


def _source(request):
    origin = request.headers.get("origin")
    if origin is not None:
        return origin
    try:
        referer = urlsplit(request.headers.get("referer", ""))
    except ValueError:
        return None
    return f"{referer.scheme}://{referer.netloc}" if referer.netloc else None


class AccountBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        route = (request.method, request.url.path)
        if route == ("GET", "/api/health"):
            return await self.app(scope, receive, send)

        async def private_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store"
                headers["Referrer-Policy"] = "no-referrer"
            await send(message)

        accounts = request.app.state.accounts
        safe = request.method in {"GET", "HEAD", "OPTIONS"}
        source = _source(request)
        if (request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}
                or (source is not None and source != accounts.origin)
                or (not safe and source != accounts.origin)):
            response = JSONResponse({"detail": "请求来源与站点不符", "code": "invalid_origin"}, status_code=403)
            return await response(scope, receive, private_send)
        if route in PUBLIC_AUTH:
            return await self.app(scope, receive, private_send)

        user = accounts.authenticate(request.cookies.get(accounts.cookie_name), touch=route != ("GET", "/api/auth/session"))
        expected = request.headers.get("x-account-id")
        if not user or (expected is not None and expected != user.id):
            response = JSONResponse({"detail": "请登录后继续", "code": "auth_required"}, status_code=401)
            return await response(scope, receive, private_send)
        request.state.user = user
        with using_account_ai(user.id, accounts.model_request):
            await self.app(scope, receive, private_send)
