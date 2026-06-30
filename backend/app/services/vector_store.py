from __future__ import annotations

import hashlib
import re
from typing import Any

import chromadb
from chromadb.config import Settings

from app.core.config import get_settings


class VectorStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(
            path=get_settings().chroma_path,
            settings=Settings(
                anonymized_telemetry=False,
                chroma_product_telemetry_impl="app.core.chroma_telemetry.NoOpProductTelemetryClient",
                chroma_telemetry_impl="app.core.chroma_telemetry.NoOpProductTelemetryClient",
            ),
        )

    @staticmethod
    def collection_name(knowledge_base_id: str, embedding_model: str) -> str:
        safe_model = re.sub(r"[^a-zA-Z0-9_-]", "-", embedding_model)[:30].strip("-") or "model"
        digest = hashlib.sha1(embedding_model.encode("utf-8")).hexdigest()[:10]
        return f"kb-{knowledge_base_id[:8]}-{safe_model}-{digest}"[:63]

    def collection(self, knowledge_base_id: str, embedding_model: str):
        return self.client.get_or_create_collection(
            name=self.collection_name(knowledge_base_id, embedding_model),
            metadata={"hnsw:space": "cosine", "embedding_model": embedding_model},
        )

    def upsert(self, knowledge_base_id: str, embedding_model: str, records: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
        if not records:
            return
        self.collection(knowledge_base_id, embedding_model).upsert(
            ids=[record["chunk_id"] for record in records],
            documents=[record["content"] for record in records],
            embeddings=embeddings,
            metadatas=[
                {
                    "document_id": record["document_id"],
                    "file_name": record["file_name"],
                    "page": record["page"] or 0,
                    "section_title": record["section_title"] or "",
                    "source_type": record["source_type"],
                }
                for record in records
            ],
        )

    def search(self, knowledge_base_id: str, embedding_model: str, query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        collection = self.collection(knowledge_base_id, embedding_model)
        if collection.count() == 0:
            return []
        result = collection.query(query_embeddings=[query_embedding], n_results=min(top_k, collection.count()))
        hits: list[dict[str, Any]] = []
        for index, chunk_id in enumerate((result.get("ids") or [[]])[0]):
            metadata = (result.get("metadatas") or [[]])[0][index] or {}
            distance = (result.get("distances") or [[]])[0][index]
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": metadata.get("document_id", ""),
                    "file_name": metadata.get("file_name", ""),
                    "content": (result.get("documents") or [[]])[0][index],
                    "page": metadata.get("page") or None,
                    "section_title": metadata.get("section_title") or None,
                    "vector_score": round(1.0 - float(distance), 6),
                }
            )
        return hits

    def delete_document(self, knowledge_base_id: str, embedding_model: str, document_id: str) -> None:
        self.collection(knowledge_base_id, embedding_model).delete(where={"document_id": document_id})

    def delete_collection(self, knowledge_base_id: str, embedding_model: str) -> None:
        name = self.collection_name(knowledge_base_id, embedding_model)
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
