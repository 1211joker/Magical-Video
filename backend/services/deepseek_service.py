"""
DeepSeek AI 分析服务 — 将字幕文本发送给 AI，返回四维度结构化分析
"""
import json
import re as _re
import httpx
from models.schemas import (
    AnalysisResult, OutlineItem, KeyPoint, ConclusionItem
)
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, AI_ANALYSIS_TIMEOUT


# AI 分析的系统提示词 — 思维导图为主，其他维度为辅
SYSTEM_PROMPT = """你是一个专业的视频内容分析助手。我会给你视频字幕文本，请仔细阅读后从以下五个维度进行分析。

其中 **思维导图是最重要的输出**，请投入最多精力构建一棵详尽的知识树。

## 思维导图 (mindmap) —— 核心输出

思维导图要完整呈现视频的全部知识结构。要求：
- 至少 5-7 个一级分支，覆盖视频所有核心话题
- 每个一级分支至少展开到第 4 层（根→一级→二级→三级→四级）
- 总节点数不少于 30 个，越多越好
- 每个节点文字必须包含具体信息：数字、术语、案例名、方法论名称、因果关系等。不要写"介绍""总结""分析"这种空洞标题
- 把视频中提到的所有例子、数据、方法、对比、结论都放进对应的节点
- 宁可多不可少——长视频可以到 50+ 节点

示例结构（注意每一层都是具体内容）：
"content": "机器学习过拟合问题",
"children": [
  {
    "content": "过拟合的定义与判断标准",
    "children": [
      {
        "content": "定义：模型在训练集表现好但泛化差",
        "children": [
          {"content": "训练准确率99%但测试仅85%"},
          {"content": "本质：模型记住了噪声而非规律"}
        ]
      },
      {
        "content": "判断标准",
        "children": [
          {"content": "训练/验证集准确率差距>5%需警惕"},
          {"content": "学习曲线：训练误差持续下降而验证误差回升"}
        ]
      }
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
- 保留视频中所有具体数据、案例、术语、人名、原话，不要概括化
- 去噪：去掉语气词、重复语句、广告内容
- 英文输入 → 中文输出
- 思维导图优先级最高：为保导图完整，可适当缩减大纲和要点
- 思维导图不要因 token 限制而偷工减料，必须完整
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

    async with httpx.AsyncClient(timeout=AI_ANALYSIS_TIMEOUT, proxy=None) as client:
        resp = await client.post(DEEPSEEK_API_URL, json=body, headers=headers)

        if resp.status_code != 200:
            error_detail = resp.text[:300]
            if resp.status_code == 401:
                raise RuntimeError("DeepSeek API Key 无效，请检查 .env 中的 DEEPSEEK_API_KEY")
            elif resp.status_code == 429:
                raise RuntimeError("AI 请求过于频繁，请稍后重试")
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
