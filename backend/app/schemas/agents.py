"""Contratos HTTP para recomendación e investigación literaria."""

import uuid

from pydantic import BaseModel, Field

from app.schemas.rag import RagTokenUsage


class RecommendationRequest(BaseModel):
    """Preferencias textuales y filtros opcionales de recomendación."""

    query: str = Field(min_length=3, max_length=2000)
    conversation_id: uuid.UUID | None = None
    genre_ids: list[int] = Field(default_factory=list, max_length=10)
    author_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    language_code: str | None = Field(default=None, min_length=2, max_length=10)
    max_pages: int | None = Field(default=None, gt=0, le=10000)
    limit: int = Field(default=5, ge=1, le=10)


class RecommendedBook(BaseModel):
    """Candidato del catálogo seleccionado por reglas y por el modelo."""

    book_id: uuid.UUID
    title: str
    authors: list[str]
    genres: list[str]
    page_count: int | None
    score: float


class RecommendationResponse(BaseModel):
    """Recomendación explicada, persistida y medible."""

    conversation_id: uuid.UUID
    answer: str
    recommendations: list[RecommendedBook]
    usage: RagTokenUsage


class ResearchRequest(BaseModel):
    """Consulta de investigación y límites de recuperación."""

    query: str = Field(min_length=3, max_length=2000)
    conversation_id: uuid.UUID | None = None
    top_k: int = Field(default=4, ge=1, le=10)
    max_external_sources: int = Field(default=4, ge=1, le=8)


class ResearchSource(BaseModel):
    """Fuente interna o externa citada por la investigación."""

    provider: str
    title: str
    url: str | None
    excerpt: str | None = None


class ResearchResponse(BaseModel):
    """Resultado de investigación con fuentes y consumo atribuido."""

    conversation_id: uuid.UUID
    answer: str
    sources: list[ResearchSource]
    usage: RagTokenUsage
