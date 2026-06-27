"""
应用配置 — 所有配置项通过环境变量读取，有默认值兜底
"""
import os

# DeepSeek AI 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 网络代理（访问 YouTube 用，可选）
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")

# 下载配置
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB 上限
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 流式转发时每次读 1MB

# 限流配置
AI_RATE_LIMIT_PER_MIN = 10  # 每个 IP 每分钟最多 10 次 AI 分析
MAX_CONCURRENT_TASKS = 2  # 同一用户同时最多 2 个任务

# 超时配置
AI_ANALYSIS_TIMEOUT = 30  # AI 分析超时秒数
YTDLP_TIMEOUT = 60  # yt-dlp 单次调用最长等待时间
