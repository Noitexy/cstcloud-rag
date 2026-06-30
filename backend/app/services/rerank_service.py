from app.clients.cstcloud_client import CSTCloudClient


class RerankService:
    def __init__(self, client: CSTCloudClient | None = None) -> None:
        self.client = client or CSTCloudClient()

    async def rerank(self, query: str, candidates: list[dict], model: str, top_n: int) -> list[dict]:
        if not candidates:
            return []
        results = await self.client.rerank(model, query, [item["content"] for item in candidates], min(top_n, len(candidates)))
        ranked: list[dict] = []
        for result in results:
            index = int(result.get("index", -1))
            if 0 <= index < len(candidates):
                item = dict(candidates[index])
                item["rerank_score"] = float(result.get("relevance_score", result.get("score", 0.0)))
                ranked.append(item)
        return ranked
