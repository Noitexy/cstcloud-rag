from fastapi import APIRouter

from app.clients.cstcloud_client import CSTCloudAPIError, CSTCloudClient
from app.core.security import api_key_configured
from app.models.schemas import ModelInfo, ModelsResponse

router = APIRouter(prefix="/models", tags=["models"])

FALLBACK_MODELS = [
    "deepseek-v4-flash",
    "minimax-m27",
    "deepseek-v3.2",
    "qwen3.5",
    "gpt-oss-120b",
    "bge-large-zh:latest",
    "gte-qwen2:7b",
    "qwen3-embedding:8b",
    "bge-reranker-v2-m3",
    "qwen3-reranker:8b",
    "S1-Base-Lite",
    "S1-Base-Pro",
    "S1-Base-Ultra",
]


@router.get("", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    configured = api_key_configured()
    if configured:
        try:
            models = await CSTCloudClient().list_models()
            return ModelsResponse(data=[ModelInfo(**item) for item in models], source="remote", api_key_configured=True)
        except CSTCloudAPIError as exc:
            warning = f"远程模型列表获取失败，已使用内置候选：{exc}"
    else:
        warning = "未配置 CSTCLOUD_API_KEY，当前展示内置候选模型。"
    return ModelsResponse(
        data=[ModelInfo(id=item, object="model", owned_by="CSTCloud") for item in FALLBACK_MODELS],
        source="fallback",
        api_key_configured=configured,
        warning=warning,
    )
