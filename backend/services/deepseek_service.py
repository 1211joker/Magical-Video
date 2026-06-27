"""
DeepSeek AI 分析服务 — 将字幕文本发送给 AI，返回结构化摘要
"""
import json
import httpx
from models.schemas import AnalysisResult
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, AI_ANALYSIS_TIMEOUT


# AI 分析的系统提示词
SYSTEM_PROMPT = """你是一个专业的视频内容分析助手。我会给你视频字幕文本，请你帮我做三件事：

1. **核心摘要**：用 2-3 句话概括视频的核心内容，语言简洁有力。
2. **关键要点**：列出 3-5 个关键要点，每个要点一句话说清楚。
3. **思维导图**：把视频内容组织成层级结构，方便生成脑图。用嵌套的 JSON 格式表达，根节点是视频主题，下面分 2-4 个大类，每个大类下面有若干具体点。

请严格按以下 JSON 格式回复（不要加其他文字）：
{
  "summary": "核心摘要内容...",
  "key_points": ["要点1", "要点2", "要点3"],
  "mindmap": {
    "content": "视频主题",
    "children": [
      {
        "content": "大类A",
        "children": [
          {"content": "具体点1"},
          {"content": "具体点2"}
        ]
      }
    ]
  }
}

注意：
- 如果字幕是英文，请用中文输出分析结果。
- 去掉字幕中的语气词（如"嗯""啊""然后"），保留实质内容。
- 遇到明显是广告/推广的内容，如实标注。
"""


async def analyze_subtitles(
    subtitle_text: str,
    video_title: str = "",
) -> AnalysisResult:
    """
    调用 DeepSeek API 分析字幕文本。

    参数：
    - subtitle_text: 字幕纯文本
    - video_title: 视频标题（用于上下文）

    返回 AnalysisResult（摘要 + 要点 + 脑图结构）。
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DeepSeek API Key 未配置，请在 backend/.env 中设置 DEEPSEEK_API_KEY")

    # 截断过长字幕（DeepSeek 上下文长度够大，但控制成本）
    max_chars = 8000
    if len(subtitle_text) > max_chars:
        # 取前 60% 和后 20%，中间部分通常不太重要
        head = subtitle_text[:int(max_chars * 0.6)]
        tail = subtitle_text[-int(max_chars * 0.2):]
        subtitle_text = head + "\n...(中间省略)...\n" + tail

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
        "temperature": 0.3,  # 低温度，输出更稳定
        "max_tokens": 2000,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=AI_ANALYSIS_TIMEOUT) as client:
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

    # 提取 AI 回复文本
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError("AI 返回格式异常，请重试")

    # 解析 JSON（AI 可能返回 markdown 代码块包裹的 JSON）
    content = content.strip()
    # 去掉可能的 ```json 和 ``` 包裹
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # 尝试提取 JSON 对象
        import re
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            parsed = json.loads(match.group())
        else:
            raise RuntimeError("AI 分析结果格式异常，请重试")

    summary = parsed.get("summary", "")
    key_points = parsed.get("key_points", [])
    mindmap = parsed.get("mindmap", {"content": video_title or "视频分析", "children": []})

    # 确保 key_points 是列表
    if isinstance(key_points, str):
        key_points = [key_points]

    # 确保 mindmap 有基本结构
    if not mindmap.get("content"):
        mindmap["content"] = video_title or "视频分析"
    if "children" not in mindmap:
        mindmap["children"] = []

    return AnalysisResult(
        title=video_title,
        summary=summary,
        key_points=key_points[:5],  # 最多 5 个要点
        mindmap=mindmap,
    )
