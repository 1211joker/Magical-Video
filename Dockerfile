# 后端 Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（yt-dlp 需要 ffmpeg 部分场景）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY backend/ .

# 创建临时文件目录
RUN mkdir -p /tmp/ytdlp_dl

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
