from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, AsyncIterator

from sqlalchemy.orm import Session

from app.clients.cstcloud_client import CSTCloudClient
from app.models.db import Conversation, ModelConfig
from app.models.schemas import ChatRequest, ChatResponse, Citation, ConversationCreate
from app.prompts.no_rag_prompt import NO_RAG_SYSTEM_PROMPT
from app.prompts.rag_answer_prompt import RAG_SYSTEM_PROMPT, build_rag_prompt
from app.services.conversation_service import ConversationService
from app.services.retrieval_service import RetrievalOptions, RetrievalService, options_from_config


@dataclass(slots=True)
class PreparedChat:
    conversation: Conversation
    history: list[dict[str, str]]
    messages: list[dict[str, str]]
    citations: list[Citation]
    retrieval_ms: float
    rewritten_query: str | None
    rag_enabled: bool
    options: RetrievalOptions


class ChatService:
    def __init__(self) -> None:
        self.client = CSTCloudClient()
        self.retrieval = RetrievalService()
        self.conversations = ConversationService()

    @staticmethod
    def _override(config: ModelConfig, overrides: dict[str, Any] | None, name: str) -> Any:
        return (overrides or {}).get(name, getattr(config, name))

    async def prepare(self, db: Session, request: ChatRequest) -> PreparedChat:
        config = db.get(ModelConfig, 1)
        options = options_from_config(config, request.config)
        conversation = db.get(Conversation, request.conversation_id) if request.conversation_id else None
        if request.conversation_id and not conversation:
            raise ValueError("会话不存在")
        if not conversation:
            conversation = self.conversations.create(
                db, ConversationCreate(knowledge_base_id=request.knowledge_base_id)
            )
        elif request.knowledge_base_id and conversation.knowledge_base_id != request.knowledge_base_id:
            conversation.knowledge_base_id = request.knowledge_base_id
            db.commit()

        history = self.conversations.history(db, conversation.id)
        kb_id = request.knowledge_base_id or conversation.knowledge_base_id
        rag_enabled = bool(self._override(config, request.config, "enable_rag") and kb_id)
        citations: list[Citation] = []
        rewritten_query: str | None = None
        retrieval_ms = 0.0

        if rag_enabled:
            result = await self.retrieval.search(db, kb_id, request.message, options, history)
            rewritten_query = result.rewritten_query
            retrieval_ms = result.retrieval_ms
            citations = [
                Citation(
                    index=index,
                    file_name=hit.file_name,
                    page=hit.page,
                    chunk_id=hit.chunk_id,
                    content=hit.content,
                    score=hit.score,
                    rerank_score=hit.rerank_score,
                )
                for index, hit in enumerate(result.hits, 1)
            ]
            sources = [
                {"file_name": item.file_name, "page": item.page, "chunk_id": item.chunk_id, "content": item.content}
                for item in citations
            ]
            messages = [
                {"role": "system", "content": RAG_SYSTEM_PROMPT},
                *history[-6:],
                {"role": "user", "content": build_rag_prompt(request.message, sources)},
            ]
        else:
            messages = [
                {"role": "system", "content": NO_RAG_SYSTEM_PROMPT},
                *history[-10:],
                {"role": "user", "content": request.message},
            ]

        self.conversations.add_message(db, conversation.id, "user", request.message)
        return PreparedChat(
            conversation=conversation,
            history=history,
            messages=messages,
            citations=citations,
            retrieval_ms=retrieval_ms,
            rewritten_query=rewritten_query,
            rag_enabled=rag_enabled,
            options=options,
        )

    async def chat(self, db: Session, request: ChatRequest) -> ChatResponse:
        total_started = perf_counter()
        prepared = await self.prepare(db, request)
        generation_started = perf_counter()
        response = await self.client.chat_completion(
            model=prepared.options.chat_model,
            messages=prepared.messages,
            temperature=prepared.options.temperature,
            top_p=prepared.options.top_p,
            max_length=prepared.options.max_length,
            enable_thinking=prepared.options.enable_thinking,
        )
        message_data = (response.get("choices") or [{}])[0].get("message", {})
        answer = message_data.get("content") or message_data.get("reasoning_content") or ""
        generation_ms = round((perf_counter() - generation_started) * 1000, 2)
        saved = self.conversations.add_message(
            db,
            prepared.conversation.id,
            "assistant",
            answer,
            prepared.citations,
            model=prepared.options.chat_model,
            retrieval_ms=prepared.retrieval_ms,
            generation_ms=generation_ms,
        )
        return ChatResponse(
            conversation_id=prepared.conversation.id,
            message_id=saved.id,
            answer=answer,
            citations=prepared.citations,
            model=prepared.options.chat_model,
            rewritten_query=prepared.rewritten_query,
            retrieval_ms=prepared.retrieval_ms,
            generation_ms=generation_ms,
            total_ms=round((perf_counter() - total_started) * 1000, 2),
        )

    async def stream(self, db: Session, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        total_started = perf_counter()
        prepared = await self.prepare(db, request)
        yield {
            "event": "meta",
            "data": {
                "conversation_id": prepared.conversation.id,
                "model": prepared.options.chat_model,
                "rag_enabled": prepared.rag_enabled,
            },
        }
        yield {
            "event": "retrieval",
            "data": {
                "rewritten_query": prepared.rewritten_query,
                "retrieval_ms": prepared.retrieval_ms,
                "hit_count": len(prepared.citations),
                "citations": [item.model_dump() for item in prepared.citations],
            },
        }

        generation_started = perf_counter()
        answer_parts: list[str] = []
        async for chunk in self.client.stream_chat_completion(
            model=prepared.options.chat_model,
            messages=prepared.messages,
            temperature=prepared.options.temperature,
            top_p=prepared.options.top_p,
            max_length=prepared.options.max_length,
            enable_thinking=prepared.options.enable_thinking,
        ):
            if chunk["reasoning_content"]:
                yield {"event": "reasoning", "data": {"content": chunk["reasoning_content"]}}
            if chunk["content"]:
                answer_parts.append(chunk["content"])
                yield {"event": "token", "data": {"content": chunk["content"]}}

        answer = "".join(answer_parts)
        generation_ms = round((perf_counter() - generation_started) * 1000, 2)
        saved = self.conversations.add_message(
            db,
            prepared.conversation.id,
            "assistant",
            answer,
            prepared.citations,
            model=prepared.options.chat_model,
            retrieval_ms=prepared.retrieval_ms,
            generation_ms=generation_ms,
        )
        yield {
            "event": "done",
            "data": {
                "message_id": saved.id,
                "generation_ms": generation_ms,
                "total_ms": round((perf_counter() - total_started) * 1000, 2),
            },
        }
