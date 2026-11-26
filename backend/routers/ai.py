"""查询服务端配置的 AI 模型。"""
from fastapi import APIRouter, Response

from models.schemas import AIProvidersResponse
from services.ai_client import provider_options

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/providers", response_model=AIProvidersResponse)
async def list_ai_providers(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return provider_options()
