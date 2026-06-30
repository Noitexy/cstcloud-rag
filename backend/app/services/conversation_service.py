from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.db import Conversation, Message, utcnow
from app.models.schemas import Citation, ConversationCreate, MessageResponse


class ConversationService:
    def create(self, db: Session, payload: ConversationCreate) -> Conversation:
        conversation = Conversation(title=payload.title, knowledge_base_id=payload.knowledge_base_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    def list(self, db: Session) -> list[Conversation]:
        return list(db.scalars(select(Conversation).order_by(Conversation.updated_at.desc())).all())

    def messages(self, db: Session, conversation_id: str) -> list[MessageResponse]:
        messages = db.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
        ).all()
        return [self.to_response(message) for message in messages]

    @staticmethod
    def history(db: Session, conversation_id: str, limit: int = 10) -> list[dict[str, str]]:
        messages = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            ).all()
        )
        return [{"role": item.role, "content": item.content} for item in reversed(messages)]

    @staticmethod
    def add_message(
        db: Session,
        conversation_id: str,
        role: str,
        content: str,
        citations: list[Citation] | None = None,
        **metrics,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations_json=json.dumps([item.model_dump() for item in citations or []], ensure_ascii=False),
            **metrics,
        )
        db.add(message)
        conversation = db.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = utcnow()
            if conversation.title == "新对话" and role == "user":
                conversation.title = content[:30]
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def to_response(message: Message) -> MessageResponse:
        try:
            citations = [Citation(**item) for item in json.loads(message.citations_json or "[]")]
        except (json.JSONDecodeError, TypeError, ValueError):
            citations = []
        return MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            citations=citations,
            model=message.model,
            retrieval_ms=message.retrieval_ms,
            generation_ms=message.generation_ms,
            created_at=message.created_at,
        )
