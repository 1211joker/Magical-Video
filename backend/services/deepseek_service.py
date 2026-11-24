"""
DeepSeek AI 分析服务 — 将字幕文本发送给 AI，返回四维度结构化分析
"""
import json
import re as _re
import httpx
from models.schemas import (
    AnalysisResult, OutlineItem, KeyPoint, ConclusionItem
)
from config import DEEPSEEK_API_KEY, AI_ANALYSIS_TIMEOUT
from services.deepseek_client import call_deepseek_api, RetryableError


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
    video_title: str = "",
) -> AnalysisResult:
    """调用 DeepSeek API 分析字幕文本。"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API Key 未配置，请在 backend/.env 中设置 DEEPSEEK_API_KEY")

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

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 10000,
        "stream": False,
    }

    try:
        resp = await call_deepseek_api(body, headers, timeout=AI_ANALYSIS_TIMEOUT)
    except RetryableError as e:
        if e.status_code == 429:
            raise RuntimeError("AI 请求过于频繁，请稍后重试")
        else:
            raise RuntimeError(f"AI 服务异常（{e.status_code}），请稍后重试")
    except httpx.TimeoutException:
        raise RuntimeError("AI 响应超时，请重试")

    if resp.status_code != 200:
        error_detail = resp.text[:300]
        if resp.status_code == 401:
            raise RuntimeError("DeepSeek API Key 无效，请检查 .env 中的 DEEPSEEK_API_KEY")
        elif resp.status_code == 402:
            raise RuntimeError("DeepSeek 账户余额不足，请充值后重试")
        else:
            raise RuntimeError(f"AI 分析失败（{resp.status_code}），请稍后重试")

    data = resp.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError("AI 返回格式异常，请重试")

    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = _re.search(r"\{[\s\S]*\}", content)
        if match:
            parsed = json.loads(match.group())
        else:
            raise RuntimeError("AI 分析结果格式异常，请重试")

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

    mindmap = parsed.get("mindmap", {"content": video_title or "视频分析", "children": []})
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
