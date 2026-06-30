from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ModelInfo(BaseModel):
    id: str
    object: str | None = None
    owned_by: str | None = None


class ModelsResponse(BaseModel):
    data: list[ModelInfo]
    source: Literal["remote", "fallback"]
    api_key_configured: bool
    warning: str | None = None


class ConfigResponse(ORMModel):
    chat_model: str
    embedding_model: str
    rerank_model: str
    temperature: float
    top_p: float
    max_length: int
    top_k: int
    rerank_top_n: int
    chunk_size: int
    chunk_overlap: int
    stream: bool
    enable_rag: bool
    enable_rerank: bool
    enable_hybrid_search: bool
    enable_query_rewrite: bool
    enable_thinking: bool


class ConfigUpdate(ConfigResponse):
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_length: int = Field(ge=128, le=32768)
    top_k: int = Field(ge=1, le=100)
    rerank_top_n: int = Field(ge=1, le=50)
    chunk_size: int = Field(ge=200, le=4000)
    chunk_overlap: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def validate_overlap(self) -> "ConfigUpdate":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        return self


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    embedding_model: str | None = None


class KnowledgeBaseResponse(ORMModel):
    id: str
    name: str
    description: str
    embedding_model: str
    created_at: datetime
    document_count: int = 0
    chunk_count: int = 0


class DocumentResponse(ORMModel):
    id: str
    knowledge_base_id: str
    name: str
    source_type: str
    file_size: int
    status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime


class ChunkResponse(ORMModel):
    id: str
    document_id: str
    knowledge_base_id: str
    chunk_index: int
    content: str
    page: int | None
    section_title: str | None
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", max_length=300)
    knowledge_base_id: str | None = None


class ConversationResponse(ORMModel):
    id: str
    title: str
    knowledge_base_id: str | None
    created_at: datetime
    updated_at: datetime


class Citation(BaseModel):
    index: int
    file_name: str
    page: int | None = None
    chunk_id: str
    content: str
    score: float | None = None
    rerank_score: float | None = None


class MessageResponse(ORMModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    model: str | None
    retrieval_ms: float | None
    generation_ms: float | None
    created_at: datetime


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    knowledge_base_id: str
    top_k: int | None = Field(default=None, ge=1, le=100)
    enable_hybrid_search: bool | None = None
    enable_rerank: bool | None = None
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)


class RetrievalHit(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    content: str
    page: int | None = None
    section_title: str | None = None
    score: float = 0.0
    vector_score: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None


class RetrievalResponse(BaseModel):
    query: str
    rewritten_query: str
    hits: list[RetrievalHit]
    retrieval_ms: float


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=30000)
    conversation_id: str | None = None
    knowledge_base_id: str | None = None
    config: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    citations: list[Citation]
    model: str
    rewritten_query: str | None = None
    retrieval_ms: float
    generation_ms: float
    total_ms: float


class EvalRequest(BaseModel):
    question: str = Field(min_length=1)
    expected_answer: str | None = None
    knowledge_base_id: str


class EvalResponse(BaseModel):
    answer: str
    citations_count: int
    grounded: bool
    keyword_coverage: float | None = None
    latency_ms: float
