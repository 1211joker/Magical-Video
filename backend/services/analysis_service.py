"""
AI 视频分析服务 — 将字幕文本转换为结构化分析结果
"""
from uuid import UUID

from models.schemas import (
    AnalysisResult, OutlineItem, KeyPoint, ConclusionItem
)
from config import AI_ANALYSIS_TIMEOUT
from services.ai_client import AIProvider, complete, decode_json_object


# AI 分析的系统提示词
SYSTEM_PROMPT = """你是一个专业的视频内容分析助手。我会给你视频字幕文本，请仔细阅读后从以下五个维度进行分析。

## 思维导图 (mindmap)

导图用于快速理解视频的核心内容。
- 最多三层（根主题 → 一级主题 → 支撑要点）。一般归纳为 3–5 个一级主题，短视频可以更少。
- 每个主题最多保留 3 个帮助理解的要点。合并重复观点、相近概念和同一方法的相邻步骤。
- 节点用简短的中文短语或一句话写清一个观点。仅保留有助于区分或理解主题的例子、数字和术语。
- 详细论据、时间段和补充案例放进大纲或关键要点。

示例结构：
"content": "机器学习过拟合问题",
"children": [
  {
    "content": "识别过拟合",
    "children": [
      {"content": "训练表现好，验证表现差"},
      {"content": "训练误差下降，验证误差回升"}
    ]
  },
  {
    "content": "减少过拟合",
    "children": [
      {"content": "用正则化限制模型复杂度"},
      {"content": "验证误差回升时提前停止训练"}
    ]
  }
]

## 概述 (overview)
2-3 句话概括视频核心内容和目标受众。

## 大纲 (outline)
按时间顺序拆分成 4-8 个段落，每个段落包含时间、主题、详细内容。

## 关键要点 (key_points)
5-8 个最重要的观点，附带原话或数据作为证据。

## 总结 (conclusions)
2-4 条可执行结论。

## JSON 格式

{
  "overview": " ... ",
  "outline": [{"time": "00:00-03:20", "topic": "段落主题", "detail": "详细内容"}],
  "key_points": [{"point": "具体观点", "evidence": "原话引用"}],
  "conclusions": [{"text": "可执行结论"}],
  "mindmap": { "content": "...", "children": [...] }
}

## 分析原则
- 在大纲和关键要点中保留支撑观点的具体数据、案例、术语、人名和原话
- 去噪：去掉语气词、重复语句、广告内容
- 英文输入 → 中文输出
- JSON 必须合法，不要截断"""


async def analyze_subtitles(
    subtitle_text: str,
    video_title: str,
    provider: AIProvider,
    *,
    retry_requests: bool = True,
    session_id: UUID | None = None,
) -> AnalysisResult:
    # 更多上下文 → AI 能提取更多细节
    max_chars = 25000
    if len(subtitle_text) > max_chars:
        head = subtitle_text[:int(max_chars * 0.2)]
        mid_start = len(subtitle_text) // 2 - int(max_chars * 0.3)
        mid_end = mid_start + int(max_chars * 0.6)
        middle = subtitle_text[mid_start:mid_end]
        tail = subtitle_text[-int(max_chars * 0.2):]
        subtitle_text = (
            head + "\n...(前段省略)...\n" +
            middle + "\n...(后段省略)...\n" +
            tail
        )
        if len(subtitle_text) > max_chars + 500:
            subtitle_text = subtitle_text[:max_chars]

    user_message = f"视频标题：{video_title}\n\n字幕内容：\n{subtitle_text}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    content = await complete(
        provider, messages, max_tokens=10000, timeout=AI_ANALYSIS_TIMEOUT,
        session_id=session_id, retry_requests=retry_requests, json_object=True,
    )
    try:
        parsed = decode_json_object(content)
    except ValueError:
        raise RuntimeError("AI 分析结果格式异常，请重试") from None

    overview = parsed.get("overview", "")

    outline = []
    for item in parsed.get("outline", []):
        if isinstance(item, dict):
            outline.append(OutlineItem(
                time=item.get("time", ""),
                topic=item.get("topic", ""),
                detail=item.get("detail", "")
            ))

    key_points = []
    for item in parsed.get("key_points", []):
        if isinstance(item, str):
            key_points.append(KeyPoint(point=item))
        elif isinstance(item, dict):
            key_points.append(KeyPoint(
                point=item.get("point", ""),
                evidence=item.get("evidence", "")
            ))

    conclusions = []
    for item in parsed.get("conclusions", []):
        if isinstance(item, str):
            conclusions.append(ConclusionItem(text=item))
        elif isinstance(item, dict):
            conclusions.append(ConclusionItem(text=item.get("text", "")))

    mindmap = parsed.get("mindmap")
    if not isinstance(mindmap, dict):
        mindmap = {}
    if not mindmap.get("content"):
        mindmap["content"] = video_title or "视频分析"
    if "children" not in mindmap:
        mindmap["children"] = []

    return AnalysisResult(
        title=video_title,
        overview=overview,
        outline=outline,
        key_points=key_points,
        conclusions=conclusions,
        mindmap=mindmap,
    )
