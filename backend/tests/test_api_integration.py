from fastapi.testclient import TestClient

from app.clients.cstcloud_client import CSTCloudClient
from app.main import app


async def fake_embeddings(self, model: str, texts: list[str]) -> list[list[float]]:
    del self, model
    return [
        [float((len(text) % 7) + 1), float((sum(map(ord, text)) % 11) + 1), 1.0]
        for text in texts
    ]


def test_ingestion_and_hybrid_retrieval_without_real_api_key(monkeypatch):
    monkeypatch.setattr(CSTCloudClient, "embeddings", fake_embeddings)
    with TestClient(app) as client:
        config = client.get("/api/config").json()
        original = dict(config)
        config.update({"enable_query_rewrite": False, "enable_rerank": False, "top_k": 5, "rerank_top_n": 3})
        assert client.post("/api/config", json=config).status_code == 200

        created = client.post(
            "/api/knowledge-bases",
            json={"name": "integration-test-kb", "description": "temporary", "embedding_model": "test-embedding"},
        )
        assert created.status_code == 201, created.text
        kb_id = created.json()["id"]
        try:
            uploaded = client.post(
                f"/api/knowledge-bases/{kb_id}/documents/upload",
                files={"file": ("service.md", "# 服务等级\n\n企业版可用性为 99.95%，故障响应不超过 30 分钟。", "text/markdown")},
            )
            assert uploaded.status_code == 201, uploaded.text
            assert uploaded.json()["status"] == "ready", uploaded.text
            assert uploaded.json()["chunk_count"] >= 1

            result = client.post(
                "/api/retrieval/search",
                json={
                    "query": "企业版可用性是多少？",
                    "knowledge_base_id": kb_id,
                    "enable_rerank": False,
                    "enable_hybrid_search": True,
                    "top_k": 5,
                    "rerank_top_n": 3,
                },
            )
            assert result.status_code == 200, result.text
            assert result.json()["hits"]
            assert "99.95%" in result.json()["hits"][0]["content"]
        finally:
            client.delete(f"/api/knowledge-bases/{kb_id}")
            client.post("/api/config", json=original)
