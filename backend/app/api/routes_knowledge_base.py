from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_kb
from app.models.db import ModelConfig, get_db
from app.models.schemas import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    try:
        kb = KnowledgeBaseService().create(db, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {**KnowledgeBaseResponse.model_validate(kb).model_dump(), "document_count": 0, "chunk_count": 0}


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(db: Session = Depends(get_db)):
    return KnowledgeBaseService().list(db)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(kb_id: str, db: Session = Depends(get_db)):
    KnowledgeBaseService().delete(db, require_kb(db, kb_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{kb_id}/reindex", response_model=KnowledgeBaseResponse)
async def rebuild_knowledge_base(kb_id: str, embedding_model: str | None = None, db: Session = Depends(get_db)):
    kb = require_kb(db, kb_id)
    config = db.get(ModelConfig, 1)
    kb = await KnowledgeBaseService().rebuild_knowledge_base(
        db, kb, embedding_model or config.embedding_model, config.chunk_size, config.chunk_overlap
    )
    summary = next(item for item in KnowledgeBaseService().list(db) if item["id"] == kb.id)
    return summary
