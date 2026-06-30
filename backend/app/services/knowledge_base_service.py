from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.db import Chunk, Document, KnowledgeBase, ModelConfig
from app.models.schemas import KnowledgeBaseCreate
from app.services.document_parser import DocumentParser
from app.services.embedding_service import EmbeddingService
from app.services.text_splitter import SemanticTextSplitter
from app.services.vector_store import VectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeBaseService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.parser = DocumentParser()
        self.embedding = EmbeddingService()
        self.vector_store = VectorStore()

    def create(self, db: Session, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        config = db.get(ModelConfig, 1)
        kb = KnowledgeBase(
            name=payload.name.strip(),
            description=payload.description.strip(),
            embedding_model=payload.embedding_model or config.embedding_model,
        )
        db.add(kb)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("知识库名称已存在") from exc
        db.refresh(kb)
        return kb

    def list(self, db: Session) -> list[dict]:
        rows = db.execute(
            select(
                KnowledgeBase,
                func.count(func.distinct(Document.id)).label("document_count"),
                func.count(Chunk.id).label("chunk_count"),
            )
            .outerjoin(Document, Document.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .group_by(KnowledgeBase.id)
            .order_by(KnowledgeBase.updated_at.desc())
        ).all()
        return [
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "embedding_model": kb.embedding_model,
                "created_at": kb.created_at,
                "document_count": document_count,
                "chunk_count": chunk_count,
            }
            for kb, document_count, chunk_count in rows
        ]

    def delete(self, db: Session, kb: KnowledgeBase) -> None:
        self.vector_store.delete_collection(kb.id, kb.embedding_model)
        upload_root = Path(self.settings.upload_path).resolve()
        upload_dir = (upload_root / kb.id).resolve()
        db.delete(kb)
        db.commit()
        if upload_dir.is_relative_to(upload_root) and upload_dir.exists():
            shutil.rmtree(upload_dir, ignore_errors=True)

    async def upload(self, db: Session, kb: KnowledgeBase, upload: UploadFile, chunk_size: int, chunk_overlap: int) -> Document:
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in DocumentParser.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持 {extension or '未知'} 文件，仅支持 txt/md/pdf/docx/csv/xlsx")
        file_size = getattr(upload, "size", None)
        if file_size and file_size > self.settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"单文件不能超过 {self.settings.max_upload_mb} MB")

        target_dir = Path(self.settings.upload_path) / kb.id
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(upload.filename or f"document{extension}").name
        target_path = target_dir / f"{uuid.uuid4().hex}_{safe_name}"
        with target_path.open("wb") as target:
            shutil.copyfileobj(upload.file, target)
        actual_size = target_path.stat().st_size
        if actual_size > self.settings.max_upload_mb * 1024 * 1024:
            target_path.unlink(missing_ok=True)
            raise ValueError(f"单文件不能超过 {self.settings.max_upload_mb} MB")

        document = Document(
            knowledge_base_id=kb.id,
            name=safe_name,
            source_type=extension.removeprefix("."),
            file_path=str(target_path),
            file_size=actual_size,
            status="processing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        await self._index_document(db, document, kb, chunk_size, chunk_overlap)
        return document

    async def _index_document(
        self,
        db: Session,
        document: Document,
        kb: KnowledgeBase,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        try:
            self.vector_store.delete_document(kb.id, kb.embedding_model, document.id)
            db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            db.flush()
            parsed = self.parser.parse(Path(document.file_path))
            split = SemanticTextSplitter(chunk_size, chunk_overlap).split(parsed)
            if not split:
                raise ValueError("文档未生成有效切片")
            chunks = [
                Chunk(
                    document_id=document.id,
                    knowledge_base_id=kb.id,
                    chunk_index=item.index,
                    content=item.content,
                    page=item.page,
                    section_title=item.section_title,
                    token_estimate=max(1, len(item.content) // 2),
                )
                for item in split
            ]
            db.add_all(chunks)
            db.flush()
            records = [
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "file_name": document.name,
                    "content": chunk.content,
                    "page": chunk.page,
                    "section_title": chunk.section_title,
                    "source_type": document.source_type,
                }
                for chunk in chunks
            ]
            vectors = await self.embedding.embed([item["content"] for item in records], kb.embedding_model)
            self.vector_store.upsert(kb.id, kb.embedding_model, records, vectors)
            document.status = "ready"
            document.error_message = None
            document.chunk_count = len(chunks)
            db.commit()
            logger.info("Document indexed: doc_id=%s kb_id=%s chunks=%s", document.id, kb.id, len(chunks))
        except Exception as exc:
            db.rollback()
            document = db.get(Document, document.id)
            if document:
                document.status = "failed"
                document.error_message = str(exc)[:1000]
                document.chunk_count = 0
                db.commit()
            logger.warning("Document index failed: doc_id=%s kb_id=%s error_type=%s", document.id if document else "unknown", kb.id, type(exc).__name__)

    async def reindex_document(self, db: Session, document: Document, chunk_size: int, chunk_overlap: int) -> Document:
        kb = db.get(KnowledgeBase, document.knowledge_base_id)
        document.status = "processing"
        db.commit()
        await self._index_document(db, document, kb, chunk_size, chunk_overlap)
        db.refresh(document)
        return document

    async def rebuild_knowledge_base(
        self, db: Session, kb: KnowledgeBase, embedding_model: str, chunk_size: int, chunk_overlap: int
    ) -> KnowledgeBase:
        old_model = kb.embedding_model
        self.vector_store.delete_collection(kb.id, old_model)
        kb.embedding_model = embedding_model
        documents = db.scalars(select(Document).where(Document.knowledge_base_id == kb.id)).all()
        db.commit()
        for document in documents:
            document.status = "processing"
            db.commit()
            await self._index_document(db, document, kb, chunk_size, chunk_overlap)
        db.refresh(kb)
        return kb

    def delete_document(self, db: Session, document: Document) -> None:
        kb = db.get(KnowledgeBase, document.knowledge_base_id)
        self.vector_store.delete_document(kb.id, kb.embedding_model, document.id)
        path = Path(document.file_path)
        db.delete(document)
        db.commit()
        upload_root = Path(self.settings.upload_path).resolve()
        resolved_path = path.resolve()
        if resolved_path.is_relative_to(upload_root):
            resolved_path.unlink(missing_ok=True)
