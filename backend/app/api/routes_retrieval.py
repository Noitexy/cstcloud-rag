from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.db import ModelConfig, get_db
from app.models.schemas import RetrievalRequest, RetrievalResponse
from app.services.retrieval_service import RetrievalService, options_from_config

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
async def search(payload: RetrievalRequest, db: Session = Depends(get_db)):
    config = db.get(ModelConfig, 1)
    overrides = {
        key: value
        for key, value in {
            "top_k": payload.top_k,
            "rerank_top_n": payload.rerank_top_n,
            "enable_hybrid_search": payload.enable_hybrid_search,
            "enable_rerank": payload.enable_rerank,
        }.items()
        if value is not None
    }
    return await RetrievalService().search(
        db, payload.knowledge_base_id, payload.query, options_from_config(config, overrides)
    )
