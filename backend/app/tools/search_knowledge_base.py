"""Agent-ready knowledge-base search adapter (reserved for a future tool registry)."""

from app.services.retrieval_service import RetrievalService


async def search_knowledge_base(*args, **kwargs):
    return await RetrievalService().search(*args, **kwargs)
