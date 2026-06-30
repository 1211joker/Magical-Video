"""
FastAPI 应用入口
"""
import logging
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
from routers import analyze, download, qa

app = FastAPI(
    title="AI 视频下载总结器",
    description="粘贴链接 → AI 摘要 → 判断是否下载",
    version="0.1.0"
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

# 注册路由
app.include_router(analyze.router)
app.include_router(download.router)
app.include_router(qa.router)


@app.get("/")
async def root():
    return {"message": "AI 视频下载总结器 API", "version": "0.1.0"}
