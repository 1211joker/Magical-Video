"""视频问答 API 路由。"""
from fastapi import APIRouter, HTTPException, Request

from limiter import limiter
from models.schemas import QaRequest, QaResponse
from services.ai_client import select_provider
from services.qa_service import answer_question

router = APIRouter(prefix="/api", tags=["qa"])


@router.post("/ask", response_model=QaResponse)
@limiter.limit("10/minute")
async def ask_question(req: QaRequest, request: Request):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    if not req.subtitle_text.strip():
        raise HTTPException(status_code=400, detail="字幕内容不能为空，请先分析视频")

    provider = select_provider(req.provider)
    return QaResponse(answer=await answer_question(req, provider))
