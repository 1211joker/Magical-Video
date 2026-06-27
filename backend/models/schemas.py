"""
Pydantic 数据模型 — 定义前后端交互的数据格式
"""
from pydantic import BaseModel
from typing import Optional


# ========== 请求模型 ==========

class ParseRequest(BaseModel):
    """解析链接请求"""
    url: str
    cookies: Optional[str] = None  # B站 cookies 文本（Netscape 格式），可选


# ========== 响应模型 ==========

class FormatInfo(BaseModel):
    """视频清晰度信息"""
    format_id: str          # yt-dlp 内部格式 ID
    resolution: str         # 给人看的清晰度，如 "1080p"
    filesize: Optional[int] = None  # 文件大小（字节），可能未知
    ext: str                # 文件格式，如 "mp4"
    has_audio: bool = True  # 是否包含音频（纯视频流为 False）


class ParseResponse(BaseModel):
    """解析链接的返回结果"""
    platform: str           # "youtube" | "bilibili" | "unsupported"
    title: str
    duration: int           # 视频时长（秒）
    thumbnail: str          # 封面图 URL
    description: str
    webpage_url: str        # 原始视频页面链接
    formats: list[FormatInfo] = []  # 可选清晰度列表


# ========== AI 分析结果模型 ==========

class SubtitleSegment(BaseModel):
    """单条字幕片段，带时间戳"""
    start_time: float       # 开始时间（秒）
    end_time: float         # 结束时间（秒）
    text: str               # 字幕文本


class OutlineItem(BaseModel):
    """大纲中的一个时间段主题"""
    time: str               # 时间段描述，如 "00:00-03:20"
    topic: str              # 该段主题
    detail: str             # 该段详细内容


class KeyPoint(BaseModel):
    """关键要点，可附带视频原文引述作为证据"""
    point: str              # 核心观点
    evidence: str = ""      # 视频原话或数据引用（可选）


class ConclusionItem(BaseModel):
    """总结/可执行结论"""
    text: str


class AnalysisResult(BaseModel):
    """AI 分析结果 — 四维度结构化输出"""
    title: str
    overview: str                       # 概述：2-3句话概括视频
    outline: list[OutlineItem] = []     # 大纲：时间段 + 主题 + 详情
    key_points: list[KeyPoint] = []     # 要点：核心观点 + 原文证据
    conclusions: list[ConclusionItem] = []  # 总结：可执行结论
    mindmap: dict = {}                  # 思维导图结构


# ========== SSE 事件模型 ==========

class ProgressEvent(BaseModel):
    """SSE 进度事件"""
    step: str               # 步骤名：parsing / subtitles / analyzing
    status: str             # processing / done / failed
    message: str = ""       # 给人看的进度描述


# ========== 通用响应 ==========

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: str = ""


# ========== 下载请求 ==========

class DownloadRequest(BaseModel):
    """下载视频请求"""
    url: str
    format_id: str = "best"     # yt-dlp 格式选择器，如 "137+140"
    cookies: Optional[str] = None
    has_audio: bool = True      # 所选格式是否已包含音频（纯视频流需后端合并）
