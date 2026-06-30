from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.db import Conversation, Document, KnowledgeBase


def require_kb(db: Session, kb_id: str) -> KnowledgeBase:
    item = db.get(KnowledgeBase, kb_id)
    if not item:
        raise HTTPException(404, "知识库不存在")
    return item


def require_document(db: Session, doc_id: str) -> Document:
    item = db.get(Document, doc_id)
    if not item:
        raise HTTPException(404, "文档不存在")
    return item


def require_conversation(db: Session, conversation_id: str) -> Conversation:
    item = db.get(Conversation, conversation_id)
    if not item:
        raise HTTPException(404, "会话不存在")
    return item
