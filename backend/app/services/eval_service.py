import re
from time import perf_counter

from sqlalchemy.orm import Session

from app.models.schemas import ChatRequest, EvalRequest, EvalResponse
from app.services.chat_service import ChatService


class EvalService:
    async def evaluate(self, db: Session, payload: EvalRequest) -> EvalResponse:
        started = perf_counter()
        result = await ChatService().chat(
            db,
            ChatRequest(
                message=payload.question,
                knowledge_base_id=payload.knowledge_base_id,
                config={"enable_rag": True},
            ),
        )
        coverage = None
        if payload.expected_answer:
            expected_terms = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]+", payload.expected_answer.lower()))
            answer_terms = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]+", result.answer.lower()))
            coverage = round(len(expected_terms & answer_terms) / max(1, len(expected_terms)), 4)
        return EvalResponse(
            answer=result.answer,
            citations_count=len(result.citations),
            grounded=bool(result.citations) and "没有找到足够依据" not in result.answer,
            keyword_coverage=coverage,
            latency_ms=round((perf_counter() - started) * 1000, 2),
        )
