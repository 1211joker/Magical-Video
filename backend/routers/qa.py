"""
AI 问答路由 — 基于视频字幕内容的问答
"""
import json
import re as _re
import httpx
from fastapi import APIRouter, HTTPException, Request
from models.schemas import QaRequest, QaResponse
from config import DEEPSEEK_API_KEY
from limiter import limiter
from services.deepseek_client import call_deepseek_api, RetryableError

router = APIRouter(prefix="/api", tags=["qa"])

# Q&A 系统提示词 — 思维链 + 批判性思考 + 亲和语气
QA_SYSTEM_PROMPT = """你是一个友好、耐心的视频内容问答伙伴。你的任务是帮助用户深入理解他们观看的视频内容。

## 核心能力

你会收到视频的字幕原文以及 AI 分析摘要（含概述、大纲、关键要点、总结）。用户会基于这些内容向你提问。

## 思维链思考流程（内部推理，不在最终回答中显式标注步骤编号）

在回答每个问题之前，请按以下步骤在脑中推理：

1. **理解意图**：用户真正想问什么？是概念解释、细节确认、观点总结、还是延伸思考？
2. **检索证据**：在字幕原文和分析摘要中定位相关信息。记住关键段落中的术语、数据、案例、人名、时间点。
3. **评估问题**：这个问题问得对吗？是否存在以下情况：
   - 问题基于错误理解 → 温和地指出并纠正
   - 问题超出视频范围 → 诚实告知并建议可以换个角度
   - 问题过于模糊 → 追问澄清，或给出几种可能的解读
   - 问题带有预设偏见 → 客观地呈现视频中的多元观点
4. **组织回答**：先给一句话直接答案，再分层展开。必要时用对比、举例、类比帮助理解。
5. **检查准确性**：回答中的每个论断都能在字幕中找到依据吗？有没有过度推断？

## 回答风格

- **语气**：像朋友聊天一样自然温暖，偶尔可以用轻松的语气词（"哈哈""嗯""其实"），但保持专业不啰嗦。
- **结构**：先一句话回答核心问题，再用要点展开细节。长回答分段，短回答直接。
- **引用**：关键论断用「」标注字幕原话作为证据。比如：「视频中讲师原话是：xxx」。
- **举例**：当概念抽象时，主动给出生活中的例子帮助理解。比如："打个比方，就像你..."
- **诚实边界**：视频没提到的内容直接说"这部分视频里没讲到哦"，可以顺便告诉用户视频里讲了哪些相关内容供参考。
- **纠错引导**：如果用户的理解有问题，不要直接否定，而是说"你的理解有一定道理，不过视频里的说法其实是这样的..."，然后给出正确解读。
- **延伸建议**：回答完问题后，如果觉得用户可能还想了解相关话题，可以提示"如果你想，我还可以告诉你视频里关于 xxx 的部分"。

## 示例对话

用户问："这个视频是不是在说 AI 会取代人类？"
好的回答：
> 嗯，你的担忧很多人都有～不过这个视频的观点其实更 nuanced。讲师并没有简单地说 AI 会取代人类，而是区分了两种情况：
> - **重复性工作**：讲师明确说"数据录入、客服问答这类标准化任务，3-5 年内大概率会被 AI 接管"，「」里是原话。
> - **创造性工作**：他认为"AI 是工具而非替代品，最终决策还是需要人的判断力"。
>
> 打个比方：就像计算器没有取代数学家，而是让他们从繁琐计算中解脱出来做更高层次的工作。AI 更像是一个超强的助手，帮我们处理重复劳动，让我们专注于更需要创造力和判断力的事情。
>
> 如果你想，我还可以展开说说视频里提到的"人机协作"模式～

## 语言要求

- 用户用中文提问 → 中文回答（默认）
- 字幕中的英文术语保留原文，首次出现时括号标注中文，如 "fine-tuning（微调）"
- 回答中不要出现 Markdown 表格或代码块，用自然段落表达

现在，请仔细阅读以下上下文信息，准备好回答用户的问题。记住：先思考，再回答。"""


@router.post("/ask", response_model=QaResponse)
@limiter.limit("10/minute")
async def ask_question(req: QaRequest, request: Request):
    """
    基于视频字幕内容回答用户问题。

    前端调用方式：
        POST /api/ask
        Body: {
            "question": "视频中提到的三种方法分别是什么？",
            "subtitle_text": "...",
            "analysis_summary": "..."
        }
    """
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="DeepSeek API Key 未配置")

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    if not req.subtitle_text.strip():
        raise HTTPException(status_code=400, detail="字幕内容不能为空，请先分析视频")

    # 构建上下文：分析摘要 + 字幕文本
    context_parts = []
    if req.analysis_summary:
        context_parts.append(f"【AI 分析摘要】\n{req.analysis_summary}")

    # 字幕文本截断（保留足够上下文，但不超过 token 限制）
    max_subtitle_chars = 20000
    subtitle = req.subtitle_text
    if len(subtitle) > max_subtitle_chars:
        head = subtitle[:int(max_subtitle_chars * 0.15)]
        mid_start = len(subtitle) // 2 - int(max_subtitle_chars * 0.35)
        mid_end = mid_start + int(max_subtitle_chars * 0.7)
        middle = subtitle[mid_start:mid_end]
        tail = subtitle[-int(max_subtitle_chars * 0.15):]
        subtitle = (
            head + "\n...(前段省略)...\n" +
            middle + "\n...(后段省略)...\n" +
            tail
        )
        if len(subtitle) > max_subtitle_chars + 500:
            subtitle = subtitle[:max_subtitle_chars]

    context_parts.append(f"【视频字幕原文】\n{subtitle}")
    context = "\n\n".join(context_parts)

    user_message = f"{context}\n\n【用户问题】\n{req.question}"

    # 构建聊天消息（含历史对话）
    messages = [{"role": "system", "content": QA_SYSTEM_PROMPT}]

    # 如果有历史对话，加入上下文
    for msg in req.chat_history[-10:]:  # 最多保留最近 10 轮
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 3000,
        "stream": False,
    }

    try:
        resp = await call_deepseek_api(body, headers, timeout=60)

        if resp.status_code != 200:
            error_detail = resp.text[:300]
            if resp.status_code == 401:
                raise HTTPException(status_code=500, detail="DeepSeek API Key 无效")
            elif resp.status_code == 429:
                raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
            elif resp.status_code == 402:
                raise HTTPException(status_code=402, detail="DeepSeek 账户余额不足")
            else:
                raise HTTPException(status_code=502, detail=f"AI 服务异常（{resp.status_code}）")

        data = resp.json()

    except RetryableError as e:
        if e.status_code == 429:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")
        else:
            raise HTTPException(status_code=502, detail=f"AI 服务异常（{e.status_code}）")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI 响应超时，请重试")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"请求 AI 服务失败: {str(e)}")

    # 提取回答内容
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise HTTPException(status_code=502, detail="AI 返回格式异常")

    return QaResponse(answer=content.strip())
