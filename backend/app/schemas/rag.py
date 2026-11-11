"""Contratos HTTP para indexación y conversación RAG."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class BookIndexResponse(BaseModel):
    """Resultado de indexar o reutilizar el documento de un libro."""

    document_id: uuid.UUID
    chunks_indexed: int
    embedding_tokens: int
    unchanged: bool


class BookIndexStatus(BaseModel):
    """Estado de sincronización entre un libro y su documento vectorial."""

    book_id: uuid.UUID
    title: str
    status: str
    document_id: uuid.UUID | None
    chunks_indexed: int


class BulkIndexItem(BaseModel):
    """Resultado individual dentro de una indexación masiva."""

    book_id: uuid.UUID
    title: str
    status: str
    chunks_indexed: int = 0
    error: str | None = None


class BulkIndexResponse(BaseModel):
    """Resumen de una indexación administrativa del catálogo."""

    total: int
    indexed: int
    unchanged: int
    failed: int
    items: list[BulkIndexItem]


class ManualDocumentWrite(BaseModel):
    """Texto interno administrable que alimenta la recuperación."""

    title: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=20, max_length=200000)
    source_url: HttpUrl | None = None


class ManualDocumentRead(BaseModel):
    """Estado público de un documento interno indexado."""

    id: uuid.UUID
    title: str
    source_url: str | None
    is_active: bool
    chunks_indexed: int
    created_at: datetime
    updated_at: datetime


class RagChatRequest(BaseModel):
    """Pregunta y opciones controladas de recuperación."""

    question: str = Field(min_length=3, max_length=2000)
    conversation_id: uuid.UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=10)


class RagSourceRead(BaseModel):
    """Fuente bibliográfica que fundamentó la respuesta."""

    document_id: uuid.UUID
    chunk_id: uuid.UUID
    book_id: uuid.UUID | None
    title: str
    source_url: str | None
    distance: float


class RagTokenUsage(BaseModel):
    """Tokens atribuidos a una respuesta del bibliotecario."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class RagChatResponse(BaseModel):
    """Respuesta conversacional persistida y sustentada."""

    conversation_id: uuid.UUID
    answer: str
    sources: list[RagSourceRead]
    usage: RagTokenUsage
