from __future__ import annotations

from app.clients.cstcloud_client import CSTCloudClient
from app.core.config import get_settings


class EmbeddingService:
    def __init__(self, client: CSTCloudClient | None = None) -> None:
        self.client = client or CSTCloudClient()
        self.batch_size = get_settings().embedding_batch_size

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(await self.client.embeddings(model, texts[start : start + self.batch_size]))
        return vectors

    async def embed_query(self, query: str, model: str) -> list[float]:
        return (await self.client.embeddings(model, [query]))[0]
