from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.clients.cstcloud_client import CSTCloudAPIError, CSTCloudClient
from app.models.db import KnowledgeBase, ModelConfig
from app.models.schemas import RetrievalHit, RetrievalResponse
from app.prompts.query_rewrite_prompt import QUERY_REWRITE_SYSTEM_PROMPT, build_query_rewrite_prompt
from app.services.bm25_service import BM25Service
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import RerankService
from app.services.vector_store import VectorStore
from app.utils.logger import get_logger
from app.utils.timeit import Timer

logger = get_logger(__name__)


@dataclass(slots=True)
class RetrievalOptions:
    top_k: int
    rerank_top_n: int
    enable_hybrid_search: bool
    enable_rerank: bool
    enable_query_rewrite: bool
    chat_model: str
    rerank_model: str
    temperature: float
    top_p: float
    max_length: int
    enable_thinking: bool


class RetrievalService:
    def __init__(self) -> None:
        self.client = CSTCloudClient()
        self.embedding = EmbeddingService(self.client)
        self.vector_store = VectorStore()
        self.bm25 = BM25Service()
        self.reranker = RerankService(self.client)

    async def rewrite(self, question: str, history: list[dict[str, str]], options: RetrievalOptions) -> str:
        if not options.enable_query_rewrite:
            return question
        try:
            response = await self.client.chat_completion(
                model=options.chat_model,
                messages=[
                    {"role": "system", "content": QUERY_REWRITE_SYSTEM_PROMPT},
                    {"role": "user", "content": build_query_rewrite_prompt(question, history)},
                ],
                temperature=0.1,
                top_p=0.8,
                max_length=512,
                enable_thinking=False,
            )
            content = (response.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
            return content or question
        except CSTCloudAPIError as exc:
            logger.warning("Query rewrite skipped after API error: %s", type(exc).__name__)
            return question

    async def search(
        self,
        db: Session,
        knowledge_base_id: str,
        question: str,
        options: RetrievalOptions,
        history: list[dict[str, str]] | None = None,
    ) -> RetrievalResponse:
        kb = db.get(KnowledgeBase, knowledge_base_id)
        if not kb:
            raise ValueError("知识库不存在")
        with Timer() as timer:
            rewritten = await self.rewrite(question, history or [], options)
            query_vector = await self.embedding.embed_query(rewritten, kb.embedding_model)
            vector_hits = self.vector_store.search(kb.id, kb.embedding_model, query_vector, options.top_k)
            bm25_hits = self.bm25.search(db, kb.id, rewritten, options.top_k) if options.enable_hybrid_search else []
            candidates = self._reciprocal_rank_fusion(vector_hits, bm25_hits)
            if options.enable_rerank and candidates:
                try:
                    candidates = await self.reranker.rerank(
                        rewritten, candidates, options.rerank_model, options.rerank_top_n
                    )
                except CSTCloudAPIError as exc:
                    logger.warning("Rerank fallback used after API error: %s", type(exc).__name__)
                    candidates = candidates[: options.rerank_top_n]
            else:
                candidates = candidates[: options.rerank_top_n]
        return RetrievalResponse(
            query=question,
            rewritten_query=rewritten,
            hits=[RetrievalHit(**item) for item in candidates],
            retrieval_ms=timer.elapsed_ms,
        )

    @staticmethod
    def _reciprocal_rank_fusion(vector_hits: list[dict], bm25_hits: list[dict], k: int = 60) -> list[dict]:
        merged: dict[str, dict] = {}
        for source, weight in ((vector_hits, 0.65), (bm25_hits, 0.35)):
            for rank, item in enumerate(source, 1):
                chunk_id = item["chunk_id"]
                if chunk_id not in merged:
                    merged[chunk_id] = dict(item)
                    merged[chunk_id]["score"] = 0.0
                else:
                    merged[chunk_id].update({key: value for key, value in item.items() if value is not None})
                merged[chunk_id]["score"] += weight / (k + rank)
        ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
        if ranked:
            best = ranked[0]["score"]
            for item in ranked:
                item["score"] = round(item["score"] / best, 6)
        return ranked


def options_from_config(config: ModelConfig, overrides: dict | None = None) -> RetrievalOptions:
    overrides = overrides or {}
    value = lambda name: overrides.get(name, getattr(config, name))
    return RetrievalOptions(
        top_k=max(1, min(int(value("top_k")), 100)),
        rerank_top_n=max(1, min(int(value("rerank_top_n")), 50)),
        enable_hybrid_search=bool(value("enable_hybrid_search")),
        enable_rerank=bool(value("enable_rerank")),
        enable_query_rewrite=bool(value("enable_query_rewrite")),
        chat_model=str(value("chat_model")),
        rerank_model=str(value("rerank_model")),
        temperature=float(value("temperature")),
        top_p=float(value("top_p")),
        max_length=int(value("max_length")),
        enable_thinking=bool(value("enable_thinking")),
    )
