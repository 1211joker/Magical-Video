"""
FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analyze, download

app = FastAPI(
    title="AI 视频下载总结器",
    description="粘贴链接 → AI 摘要 → 判断是否下载",
    version="0.1.0"
)

# 允许前端跨域请求（开发阶段放开所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(analyze.router)
app.include_router(download.router)


@app.get("/")
async def root():
    return {"message": "AI 视频下载总结器 API", "version": "0.1.0"}
