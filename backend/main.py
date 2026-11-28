"""
FastAPI 应用入口
"""
import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # 加载 .env 中的环境变量

# 配置日志 — 方便调试
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from limiter import limiter
from models.auth import AuthProblem
from routers import ai, analyze, auth, download, qa, study
from routers.account_boundary import AccountBoundary
from services.ai_client import AIServiceError
from services.auth import Accounts
from services.download_service import DownloadJobs
from services.panopto_service import PanoptoError
from services.study_runtime import StudyRuntime
from services.video_session import BilibiliSessionError
from services.youtube_network import YouTubeNetworkUnavailable
from storage.data_home import data_directory, exclusive_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    directory = data_directory()
    with exclusive_data(directory):
        accounts = Accounts(directory)
        accounts.database.initialize()
        app.state.accounts = accounts
        app.state.download_jobs = DownloadJobs()
        app.state.study = None
        if os.environ.get("STUDY_ENABLED", "1") != "0":
            app.state.study = StudyRuntime(directory, accounts)
            app.state.study.start()
        try:
            yield
        finally:
            if app.state.study is not None:
                await app.state.study.close()
            await app.state.download_jobs.close()


app = FastAPI(
    title="AI 视频下载总结器",
    description="粘贴链接 → AI 摘要 → 判断是否下载",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if os.getenv("APP_ENV") == "production" else "/docs",
    redoc_url=None if os.getenv("APP_ENV") == "production" else "/redoc",
    openapi_url=None if os.getenv("APP_ENV") == "production" else "/openapi.json",
)

app.add_middleware(AccountBoundary)

# 限流配置 — slowapi，通过请求 IP 识别调用方
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(AIServiceError)
async def handle_ai_error(_request: Request, error: AIServiceError):
    return JSONResponse(status_code=error.status_code, content={"detail": str(error), "code": error.code})


@app.exception_handler(AuthProblem)
async def handle_auth_error(_request: Request, error: AuthProblem):
    return JSONResponse(status_code=error.status, content={"detail": str(error), "code": error.code})


@app.exception_handler(RequestValidationError)
async def handle_invalid_request(_request: Request, _error: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "请求参数格式无效", "code": "invalid_request"})


@app.exception_handler(YouTubeNetworkUnavailable)
async def handle_youtube_network_unavailable(_request: Request, error: YouTubeNetworkUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(error), "code": error.code})


@app.exception_handler(PanoptoError)
async def handle_panopto_error(_request: Request, error: PanoptoError):
    status = {
        "panopto_login_required": 401,
        "panopto_session_rejected": 401,
        "panopto_download_unavailable": 403,
        "panopto_network_unavailable": 503,
        "panopto_unavailable": 502,
    }.get(error.code, 400)
    return JSONResponse(
        status_code=status,
        content={"detail": str(error), "code": error.code},
        headers={"Cache-Control": "no-store"},
    )


@app.exception_handler(BilibiliSessionError)
async def handle_bilibili_session_error(_request: Request, error: BilibiliSessionError):
    return JSONResponse(
        status_code=401,
        content={"detail": str(error), "code": error.code},
        headers={"Cache-Control": "no-store"},
    )


# 注册路由
app.include_router(auth.router)
app.include_router(ai.router)
app.include_router(analyze.router)
app.include_router(download.router)
app.include_router(qa.router)
app.include_router(study.router)


@app.get("/")
async def root():
    return {"message": "AI 视频下载总结器 API", "version": "0.1.0"}
