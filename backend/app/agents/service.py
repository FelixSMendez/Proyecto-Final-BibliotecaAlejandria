"""Orquestación de recomendación e investigación literaria."""

import re
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.external import ExternalResearchClient, ExternalSourceData
from app.agents.prompts import RECOMMENDATION_INSTRUCTIONS, RESEARCH_INSTRUCTIONS
from app.models import (
    AiService,
    Book,
    Conversation,
    ExternalSource,
    Message,
    ServiceExecution,
    User,
)
from app.rag.providers import AiProvider
from app.rag.service import (
    get_conversation,
    record_failed_execution,
    retrieve_sources,
)
from app.repositories.catalog import book_load_options
from app.schemas.agents import RecommendationRequest, ResearchRequest
from app.services.usage import assert_token_budget, register_token_usage


@dataclass(frozen=True)
class RecommendedBookResult:
    """Libro puntuado que fundamenta una recomendación."""

    book_id: uuid.UUID
    title: str
    authors: list[str]
    genres: list[str]
    page_count: int | None
    score: float


@dataclass(frozen=True)
class AgentSourceResult:
    """Fuente normalizada que sustenta una investigación."""

    provider: str
    title: str
    url: str | None
    excerpt: str | None


@dataclass(frozen=True)
class RecommendationResult:
    """Respuesta del recomendador lista para la capa HTTP."""

    conversation_id: uuid.UUID
    answer: str
    recommendations: list[RecommendedBookResult]
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class ResearchResult:
    """Investigación persistida con fuentes y consumo."""

    conversation_id: uuid.UUID
    answer: str
    sources: list[AgentSourceResult]
    prompt_tokens: int
    completion_tokens: int


def get_active_service(db: Session, code: str) -> AiService:
    """Obtiene un servicio de IA activo por su código estable."""
    service = db.scalar(select(AiService).where(AiService.code == code))
    if service is None or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio solicitado no está disponible",
        )
    return service


def _normalized_terms(text: str) -> set[str]:
    """Extrae términos útiles para puntuar coincidencias locales."""
    return {term for term in re.findall(r"\w+", text.lower()) if len(term) >= 3}


def score_recommendation_candidate(book: Book, request: RecommendationRequest) -> float | None:
    """Aplica filtros estrictos y una puntuación explicable al catálogo."""
    book_genres = {link.genre_id for link in book.genre_links}
    book_authors = {link.author_id for link in book.author_links}
    if request.genre_ids and not book_genres.intersection(request.genre_ids):
        return None
    if request.author_ids and not book_authors.intersection(request.author_ids):
        return None
    if request.language_code and book.language_code.lower() != request.language_code.lower():
        return None
    if request.max_pages and book.page_count is not None and book.page_count > request.max_pages:
        return None

    searchable = " ".join(
        [
            book.title,
            book.subtitle or "",
            book.synopsis or "",
            *(link.author.full_name for link in book.author_links),
            *(link.genre.name for link in book.genre_links),
        ]
    )
    lexical_matches = len(
        _normalized_terms(request.query).intersection(_normalized_terms(searchable))
    )
    score = min(lexical_matches, 8) * 1.25
    score += len(book_genres.intersection(request.genre_ids)) * 3
    score += len(book_authors.intersection(request.author_ids)) * 4
    score += 2 if request.language_code else 0
    score += 1 if request.max_pages and book.page_count is not None else 0
    return round(score, 2)


def select_recommendation_candidates(
    db: Session, request: RecommendationRequest
) -> list[tuple[Book, float]]:
    """Selecciona candidatos activos con relaciones precargadas."""
    statement = (
        select(Book)
        .options(*book_load_options())
        .where(Book.is_active.is_(True))
        .order_by(Book.title)
        .limit(200)
    )
    scored = []
    for book in db.scalars(statement).all():
        score = score_recommendation_candidate(book, request)
        if score is not None:
            scored.append((book, score))
    scored.sort(key=lambda item: (-item[1], item[0].title.lower()))
    return scored[: request.limit]


def _history_text(conversation: Conversation) -> str:
    """Limita el historial incluido para controlar costo y contexto."""
    messages = sorted(conversation.messages, key=lambda item: item.created_at)[-6:]
    return "\n".join(f"{message.role}: {message.content}" for message in messages)


def _provider_model(provider: AiProvider, kind: str) -> str | None:
    """Obtiene el modelo configurado sin ampliar el contrato del proveedor."""
    provider_settings = getattr(provider, "settings", None)
    field = "ai_embedding_model" if kind == "embedding" else "ai_chat_model"
    return getattr(provider_settings, field, None)


def recommend_books(
    db: Session,
    *,
    user: User,
    request: RecommendationRequest,
    provider: AiProvider,
) -> RecommendationResult:
    """Puntúa el catálogo y genera recomendaciones razonadas."""
    service = get_active_service(db, "book_recommender")
    conversation = get_conversation(
        db,
        conversation_id=request.conversation_id,
        user=user,
        service=service,
        question=request.query,
    )
    started = time.perf_counter()
    try:
        candidates = select_recommendation_candidates(db, request)
        prompt_tokens = 0
        completion_tokens = 0
        if candidates:
            assert_token_budget(user, service.max_tokens_per_request)
            catalog_context = "\n\n".join(
                f"[Catálogo {index}] {book.title}\n"
                f"Autores: {', '.join(link.author.full_name for link in book.author_links)}\n"
                f"Géneros: {', '.join(link.genre.name for link in book.genre_links)}\n"
                f"Páginas: {book.page_count or 'sin dato'}\nSinopsis: {book.synopsis or 'sin dato'}"
                for index, (book, _) in enumerate(candidates, start=1)
            )
            prompt = (
                f"Preferencias del usuario:\n{request.query}\n\n"
                f"Historial breve:\n{_history_text(conversation) or 'Sin historial'}\n\n"
                f"Candidatos:\n{catalog_context}"
            )
            generation = provider.generate(
                instructions=RECOMMENDATION_INSTRUCTIONS,
                input_text=prompt,
                max_output_tokens=min(900, service.max_tokens_per_request),
                safety_identifier=str(user.id),
            )
            answer = generation.text
            prompt_tokens = generation.input_tokens
            completion_tokens = generation.output_tokens
        else:
            answer = "No encontré libros activos que cumplan los filtros indicados."

        recommendations = [
            RecommendedBookResult(
                book_id=book.id,
                title=book.title,
                authors=[link.author.full_name for link in book.author_links],
                genres=[link.genre.name for link in book.genre_links],
                page_count=book.page_count,
                score=score,
            )
            for book, score in candidates
        ]
        source_payload = [
            {
                "provider": "catalog",
                "book_id": str(item.book_id),
                "title": item.title,
                "score": item.score,
            }
            for item in recommendations
        ]
        conversation.messages.extend(
            [
                Message(role="user", content=request.query),
                Message(
                    role="assistant",
                    content=answer,
                    sources=source_payload,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                ),
            ]
        )
        conversation.updated_at = datetime.now(UTC)
        db.add(
            ServiceExecution(
                user_id=user.id,
                service_id=service.id,
                conversation_id=conversation.id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_name=_provider_model(provider, "chat"),
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="success",
            )
        )
        register_token_usage(user, prompt_tokens + completion_tokens)
        db.commit()
        return RecommendationResult(
            conversation.id,
            answer,
            recommendations,
            prompt_tokens,
            completion_tokens,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        record_failed_execution(
            db,
            user_id=user.id,
            service_id=service.id,
            error=exc,
            duration_ms=round((time.perf_counter() - started) * 1000),
            model_name=_provider_model(provider, "chat"),
        )
        raise


def _external_source_payload(source: ExternalSourceData) -> dict:
    """Convierte una fuente externa al formato almacenado en mensajes."""
    return {
        "provider": source.provider,
        "external_id": source.external_id,
        "title": source.title,
        "url": source.url,
    }


def research_literature(
    db: Session,
    *,
    user: User,
    request: ResearchRequest,
    provider: AiProvider,
    external_client: ExternalResearchClient,
) -> ResearchResult:
    """Contrasta contexto interno con fuentes externas y conserva evidencia."""
    service = get_active_service(db, "literary_research")
    assert_token_budget(user, service.max_tokens_per_request)
    conversation = get_conversation(
        db,
        conversation_id=request.conversation_id,
        user=user,
        service=service,
        question=request.query,
    )
    started = time.perf_counter()
    try:
        embedding = provider.embed([request.query], task_type="query")
        internal_matches = retrieve_sources(
            db,
            query_vector=embedding.vectors[0],
            top_k=request.top_k,
        )
        external_sources = external_client.search(request.query, request.max_external_sources)
        internal_context = "\n\n".join(
            f"[Catálogo {index}] {document.title}\n{chunk.content}"
            for index, (chunk, document, _) in enumerate(internal_matches, start=1)
        )
        external_context = "\n\n".join(
            f"[Externa {index}] {source.title}\nURL: {source.url}\n{source.excerpt}"
            for index, source in enumerate(external_sources, start=1)
        )
        generation_input_tokens = 0
        completion_tokens = 0
        if internal_matches or external_sources:
            prompt = (
                f"Pregunta de investigación:\n{request.query}\n\n"
                f"Historial breve:\n{_history_text(conversation) or 'Sin historial'}\n\n"
                f"Catálogo interno:\n{internal_context or 'Sin resultados'}\n\n"
                f"Fuentes externas:\n{external_context or 'Sin resultados'}"
            )
            generation = provider.generate(
                instructions=RESEARCH_INSTRUCTIONS,
                input_text=prompt,
                max_output_tokens=min(2000, service.max_tokens_per_request),
                safety_identifier=str(user.id),
            )
            answer = generation.text
            generation_input_tokens = generation.input_tokens
            completion_tokens = generation.output_tokens
        else:
            answer = "No encontré fuentes suficientes para elaborar una investigación confiable."

        internal_results = [
            AgentSourceResult("catalog", document.title, document.source_url, chunk.content[:500])
            for chunk, document, _ in internal_matches
        ]
        external_results = [
            AgentSourceResult(source.provider, source.title, source.url, source.excerpt[:500])
            for source in external_sources
        ]
        source_payload = [
            {
                "provider": source.provider,
                "title": source.title,
                "url": source.url,
            }
            for source in [*internal_results, *external_results]
        ]
        conversation.messages.extend(
            [
                Message(role="user", content=request.query),
                Message(
                    role="assistant",
                    content=answer,
                    sources=source_payload,
                    prompt_tokens=embedding.input_tokens + generation_input_tokens,
                    completion_tokens=completion_tokens,
                ),
            ]
        )
        for source in external_sources:
            conversation.external_sources.append(
                ExternalSource(
                    provider=source.provider,
                    external_id=source.external_id,
                    title=source.title,
                    url=source.url,
                    excerpt=source.excerpt,
                    source_metadata=source.metadata,
                )
            )
        conversation.updated_at = datetime.now(UTC)
        prompt_tokens = embedding.input_tokens + generation_input_tokens
        db.add(
            ServiceExecution(
                user_id=user.id,
                service_id=service.id,
                conversation_id=conversation.id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_name=(
                    f"{_provider_model(provider, 'embedding')} + "
                    f"{_provider_model(provider, 'chat')}"
                ),
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="success",
            )
        )
        register_token_usage(user, prompt_tokens + completion_tokens)
        db.commit()
        return ResearchResult(
            conversation.id,
            answer,
            [*internal_results, *external_results],
            prompt_tokens,
            completion_tokens,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        record_failed_execution(
            db,
            user_id=user.id,
            service_id=service.id,
            error=exc,
            duration_ms=round((time.perf_counter() - started) * 1000),
            model_name=_provider_model(provider, "chat"),
        )
        raise
