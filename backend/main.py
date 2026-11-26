"""
FastAPI 应用入口
"""
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from secrets import token_urlsafe
from dotenv import load_dotenv
load_dotenv()  # 加载 .env 中的环境变量

# 配置日志 — 方便调试
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from config import ALLOWED_ORIGINS
from limiter import limiter
from routers import ai, analyze, download, qa, study
from services.ai_client import AIServiceError
from services.download_service import DownloadJobs
from services.panopto_service import PanoptoError
from services.study import StudyService
from services.video_session import BilibiliSessionError
from services.youtube_network import YouTubeNetworkUnavailable


@asynccontextmanager
async def lifespan(app: FastAPI):
    download_jobs = DownloadJobs()
    app.state.download_jobs = download_jobs
    app.state.study = None
    app.state.study_token = None
    if os.environ.get("STUDY_ENABLED", "1") != "0":
        local_study = StudyService()
        try:
            local_study.start()
        except (OSError, RuntimeError, sqlite3.Error):
            logging.getLogger(__name__).warning("本地资料库无法初始化")
        else:
            app.state.study = local_study
            app.state.study_token = token_urlsafe(32)
    try:
        yield
    finally:
        if app.state.study is not None:
            await app.state.study.close()
        await download_jobs.close()


app = FastAPI(
    title="AI 视频下载总结器",
    description="粘贴链接 → AI 摘要 → 判断是否下载",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 跨域配置 — 通过环境变量 ALLOWED_ORIGINS 控制
# 未设置或设为 * 时允许所有来源（开发模式）
# 生产环境：ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
origins = ALLOWED_ORIGINS.split(",") if ALLOWED_ORIGINS and ALLOWED_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流配置 — slowapi，通过请求 IP 识别调用方
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(AIServiceError)
async def handle_ai_error(_request: Request, error: AIServiceError):
    return JSONResponse(status_code=error.status_code, content={"detail": str(error)})


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
app.include_router(ai.router)
app.include_router(analyze.router)
app.include_router(download.router)
app.include_router(qa.router)
app.include_router(study.router)


@app.get("/")
async def root():
    return {"message": "AI 视频下载总结器 API", "version": "0.1.0"}
