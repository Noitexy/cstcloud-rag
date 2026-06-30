from __future__ import annotations

import re

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.db import Chunk, Document


def tokenize(text: str) -> list[str]:
    text = text.lower()
    latin = re.findall(r"[a-z0-9_+-]+", text)
    han = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    return latin + list(han) + [han[i : i + 2] for i in range(max(0, len(han) - 1))]


class BM25Service:
    def search(self, db: Session, knowledge_base_id: str, query: str, top_k: int) -> list[dict]:
        rows = db.execute(
            select(Chunk, Document.name)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.knowledge_base_id == knowledge_base_id, Document.status == "ready")
        ).all()
        if not rows:
            return []
        corpus = [tokenize(chunk.content) for chunk, _ in rows]
        if not any(corpus):
            return []
        scores = BM25Okapi(corpus).get_scores(tokenize(query))
        best = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)[:top_k]
        max_score = max((float(scores[i]) for i in best), default=0.0)
        return [
            {
                "chunk_id": rows[i][0].id,
                "document_id": rows[i][0].document_id,
                "file_name": rows[i][1],
                "content": rows[i][0].content,
                "page": rows[i][0].page,
                "section_title": rows[i][0].section_title,
                "bm25_score": round(float(scores[i]) / max_score, 6) if max_score > 0 else 0.0,
            }
            for i in best
            if scores[i] > 0
        ]
