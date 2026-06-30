from fastapi import HTTPException, status

from app.core.config import get_settings


def api_key_configured() -> bool:
    return bool(get_settings().cstcloud_api_key)


def require_api_key() -> str:
    key = get_settings().cstcloud_api_key
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置 CSTCLOUD_API_KEY，请在 backend/.env 中配置后重试。",
        )
    return key
