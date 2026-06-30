from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings. Secrets are accepted only from the environment."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "CSTCloud-RAG 智能知识库问答系统"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"
    debug: bool = False
    cstcloud_api_key: str | None = Field(default=None, repr=False)
    cstcloud_base_url: str = "https://uni-api.cstcloud.cn/v1"
    request_timeout: float = 120.0
    request_retries: int = 2
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'cstcloud_rag.db').as_posix()}"
    chroma_path: str = str(BACKEND_DIR / "data" / "chroma")
    upload_path: str = str(BACKEND_DIR / "data" / "uploads")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: int = 50
    embedding_batch_size: int = 16

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def ensure_directories(self) -> None:
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        Path(self.upload_path).mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
