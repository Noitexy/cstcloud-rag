from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_document, require_kb
from app.models.db import Chunk, Document, ModelConfig, get_db
from app.models.schemas import ChunkResponse, DocumentResponse
from app.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(tags=["documents"])


@router.post(
    "/knowledge-bases/{kb_id}/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(kb_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    kb = require_kb(db, kb_id)
    config = db.get(ModelConfig, 1)
    try:
        return await KnowledgeBaseService().upload(db, kb, file, config.chunk_size, config.chunk_overlap)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[DocumentResponse])
def list_documents(kb_id: str, db: Session = Depends(get_db)):
    require_kb(db, kb_id)
    return db.scalars(
        select(Document).where(Document.knowledge_base_id == kb_id).order_by(Document.created_at.desc())
    ).all()


@router.get("/documents/{doc_id}/chunks", response_model=list[ChunkResponse])
def list_chunks(doc_id: str, db: Session = Depends(get_db)):
    require_document(db, doc_id)
    return db.scalars(select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.chunk_index)).all()


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: str, db: Session = Depends(get_db)):
    KnowledgeBaseService().delete_document(db, require_document(db, doc_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{doc_id}/reindex", response_model=DocumentResponse)
async def reindex_document(doc_id: str, db: Session = Depends(get_db)):
    config = db.get(ModelConfig, 1)
    return await KnowledgeBaseService().reindex_document(
        db, require_document(db, doc_id), config.chunk_size, config.chunk_overlap
    )
