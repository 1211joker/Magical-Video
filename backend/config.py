"""
应用配置 — 所有配置项通过环境变量读取，有默认值兜底
"""
import os

# DeepSeek AI 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 网络代理（访问 YouTube 用，可选）
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")

# yt-dlp SSL 证书验证（默认开启，仅在国内网络劫持环境下临时关闭）
YTDLP_NO_CHECK_CERTIFICATES = os.getenv("YTDLP_NO_CHECK_CERTIFICATES", "false").lower() == "true"

# CORS 配置
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")  # 生产环境设置具体域名，逗号分隔多个

# 限流配置
AI_RATE_LIMIT_PER_MIN = 10  # 每个 IP 每分钟最多 10 次 AI 分析
MAX_CONCURRENT_TASKS = 2  # 同一用户同时最多 2 个任务

# 超时配置
AI_ANALYSIS_TIMEOUT = 120  # AI 分析超时秒数（长字幕 + 10000 tokens + 思维导图需要较长时间）
YTDLP_TIMEOUT = 60  # yt-dlp 元数据查询最长等待时间
DOWNLOAD_TIMEOUT = 600  # 实际下载最长等待时间（10分钟，视频文件较大）
