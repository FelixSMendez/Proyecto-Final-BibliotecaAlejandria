"""Orquestación de indexación, recuperación y respuesta conversacional."""

import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.models import (
    AiService,
    Book,
    Conversation,
    Document,
    DocumentChunk,
    Message,
    ServiceExecution,
    User,
)
from app.rag.chunking import build_book_document, estimate_tokens, split_text
from app.rag.prompts import RAG_INSTRUCTIONS, PromptChunk, build_rag_input
from app.rag.providers import AiProvider
from app.services.usage import assert_token_budget, register_token_usage


@dataclass(frozen=True)
class IndexResult:
    """Resultado observable de indexar una fuente bibliográfica."""

    document_id: uuid.UUID
    chunks_indexed: int
    embedding_tokens: int
    unchanged: bool


@dataclass(frozen=True)
class _PreparedBookIndex:
    """Contenido y documento preparados antes de solicitar embeddings en lote."""

    book: Book
    document: Document | None
    content_hash: str
    chunks: list[str]


@dataclass(frozen=True)
class RetrievedSource:
    """Fuente recuperada y lista para exponerse al usuario."""

    document_id: uuid.UUID
    chunk_id: uuid.UUID
    book_id: uuid.UUID | None
    title: str
    source_url: str | None
    distance: float


@dataclass(frozen=True)
class AnswerResult:
    """Respuesta RAG persistida con fuentes y uso real."""

    conversation_id: uuid.UUID
    answer: str
    sources: list[RetrievedSource]
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class BookIndexState:
    """Estado calculado de sincronización de un libro."""

    book_id: uuid.UUID
    title: str
    status: str
    document_id: uuid.UUID | None
    chunks_indexed: int


def get_rag_service(db: Session) -> AiService:
    """Obtiene el servicio principal y verifica que esté habilitado."""
    service = db.scalar(select(AiService).where(AiService.code == "rag_librarian"))
    if service is None or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El bibliotecario virtual no está disponible",
        )
    return service


def record_failed_execution(
    db: Session,
    *,
    user_id: uuid.UUID,
    service_id: int,
    error: Exception,
    duration_ms: int | None = None,
    model_name: str | None = None,
) -> None:
    """Registra un fallo de proveedor sin conservar una transacción parcial."""
    db.rollback()
    db.add(
        ServiceExecution(
            user_id=user_id,
            service_id=service_id,
            status="failed",
            error_message=str(error)[:1000],
            duration_ms=duration_ms,
            model_name=model_name,
        )
    )
    db.commit()


def index_book(
    db: Session,
    *,
    book: Book,
    user: User,
    provider: AiProvider,
    settings: Settings,
) -> IndexResult:
    """Regenera los fragmentos vectoriales de un libro cuando cambió su contenido."""
    started = time.perf_counter()
    service = get_rag_service(db)
    service_id = service.id
    content = build_book_document(book)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    statement = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.book_id == book.id, Document.source_type == "book_catalog")
    )
    document = db.scalar(statement)
    if document and document.content_hash == content_hash and document.chunks:
        if not document.is_active:
            document.is_active = True
            db.commit()
        return IndexResult(document.id, len(document.chunks), 0, True)

    chunks = split_text(
        content,
        chunk_size=settings.rag_chunk_size,
        overlap=settings.rag_chunk_overlap,
    )
    if not chunks:
        raise ValueError("El libro no contiene información suficiente para indexar")

    estimated_tokens = sum(estimate_tokens(chunk) for chunk in chunks)
    assert_token_budget(user, estimated_tokens)
    try:
        embedding_batch = provider.embed(chunks, task_type="document")
        if len(embedding_batch.vectors) != len(chunks):
            raise RuntimeError("El proveedor devolvió una cantidad inesperada de embeddings")
        if any(
            len(vector) != settings.ai_embedding_dimensions
            for vector in embedding_batch.vectors
        ):
            raise RuntimeError("La dimensión del embedding no coincide con la base vectorial")

        if document is None:
            document = Document(
                book_id=book.id,
                title=book.title,
                source_type="book_catalog",
                source_url=book.source_url,
                content_hash=content_hash,
            )
            db.add(document)
            db.flush()
        else:
            document.title = book.title
            document.source_url = book.source_url
            document.content_hash = content_hash
            document.is_active = True
            document.chunks.clear()
            db.flush()

        document.chunks = [
            DocumentChunk(
                chunk_index=index,
                content=chunk,
                token_count=estimate_tokens(chunk),
                chunk_metadata={"book_id": str(book.id), "title": book.title},
                embedding=vector,
            )
            for index, (chunk, vector) in enumerate(
                zip(chunks, embedding_batch.vectors, strict=True)
            )
        ]
        register_token_usage(user, embedding_batch.input_tokens)
        db.add(
            ServiceExecution(
                user_id=user.id,
                service_id=service_id,
                prompt_tokens=embedding_batch.input_tokens,
                completion_tokens=0,
                model_name=settings.ai_embedding_model,
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="success",
            )
        )
        db.commit()
        return IndexResult(
            document_id=document.id,
            chunks_indexed=len(chunks),
            embedding_tokens=embedding_batch.input_tokens,
            unchanged=False,
        )
    except Exception as exc:
        record_failed_execution(
            db,
            user_id=user.id,
            service_id=service_id,
            error=exc,
            duration_ms=round((time.perf_counter() - started) * 1000),
            model_name=settings.ai_embedding_model,
        )
        raise


def index_books_batch(
    db: Session,
    *,
    books: list[Book],
    user: User,
    provider: AiProvider,
    settings: Settings,
) -> dict[uuid.UUID, IndexResult]:
    """Indexa varios libros con una sola solicitud al proveedor de embeddings."""
    if not books:
        return {}

    started = time.perf_counter()
    service = get_rag_service(db)
    service_id = service.id
    prepared: list[_PreparedBookIndex] = []
    results: dict[uuid.UUID, IndexResult] = {}
    all_chunks: list[str] = []

    for book in books:
        content = build_book_document(book)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        document = db.scalar(
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.book_id == book.id, Document.source_type == "book_catalog")
        )
        if document and document.content_hash == content_hash and document.chunks:
            if not document.is_active:
                document.is_active = True
            results[book.id] = IndexResult(document.id, len(document.chunks), 0, True)
            continue

        chunks = split_text(
            content,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )
        if not chunks:
            raise ValueError(f"El libro '{book.title}' no contiene información suficiente")
        prepared.append(_PreparedBookIndex(book, document, content_hash, chunks))
        all_chunks.extend(chunks)

    if not prepared:
        db.commit()
        return results

    estimated_tokens = sum(estimate_tokens(chunk) for chunk in all_chunks)
    assert_token_budget(user, estimated_tokens)
    try:
        embedding_batch = provider.embed(all_chunks, task_type="document")
        if len(embedding_batch.vectors) != len(all_chunks):
            raise RuntimeError("El proveedor devolvió una cantidad inesperada de embeddings")
        if any(
            len(vector) != settings.ai_embedding_dimensions
            for vector in embedding_batch.vectors
        ):
            raise RuntimeError("La dimensión del embedding no coincide con la base vectorial")

        vector_offset = 0
        for item in prepared:
            document = item.document
            if document is None:
                document = Document(
                    book_id=item.book.id,
                    title=item.book.title,
                    source_type="book_catalog",
                    source_url=item.book.source_url,
                    content_hash=item.content_hash,
                )
                db.add(document)
                db.flush()
            else:
                document.title = item.book.title
                document.source_url = item.book.source_url
                document.content_hash = item.content_hash
                document.is_active = True
                document.chunks.clear()
                db.flush()

            vectors = embedding_batch.vectors[
                vector_offset : vector_offset + len(item.chunks)
            ]
            vector_offset += len(item.chunks)
            document.chunks = [
                DocumentChunk(
                    chunk_index=index,
                    content=chunk,
                    token_count=estimate_tokens(chunk),
                    chunk_metadata={"book_id": str(item.book.id), "title": item.book.title},
                    embedding=vector,
                )
                for index, (chunk, vector) in enumerate(
                    zip(item.chunks, vectors, strict=True)
                )
            ]
            book_tokens = sum(estimate_tokens(chunk) for chunk in item.chunks)
            results[item.book.id] = IndexResult(
                document.id,
                len(item.chunks),
                book_tokens,
                False,
            )

        register_token_usage(user, embedding_batch.input_tokens)
        db.add(
            ServiceExecution(
                user_id=user.id,
                service_id=service_id,
                prompt_tokens=embedding_batch.input_tokens,
                completion_tokens=0,
                model_name=settings.ai_embedding_model,
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="success",
            )
        )
        db.commit()
        return results
    except Exception as exc:
        record_failed_execution(
            db,
            user_id=user.id,
            service_id=service_id,
            error=exc,
            duration_ms=round((time.perf_counter() - started) * 1000),
            model_name=settings.ai_embedding_model,
        )
        raise


def index_manual_document(
    db: Session,
    *,
    title: str,
    content: str,
    source_url: str | None,
    user: User,
    provider: AiProvider,
    settings: Settings,
    document: Document | None = None,
) -> IndexResult:
    """Crea o reemplaza un documento interno y sus fragmentos vectoriales."""
    started = time.perf_counter()
    service = get_rag_service(db)
    service_id = service.id
    normalized_content = content.strip()
    content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
    if document and document.source_type != "manual":
        raise ValueError("Solo se pueden editar documentos manuales")
    if document and document.content_hash == content_hash and document.chunks:
        document.title = title
        document.source_url = source_url
        document.is_active = True
        db.commit()
        return IndexResult(document.id, len(document.chunks), 0, True)

    chunks = split_text(
        normalized_content,
        chunk_size=settings.rag_chunk_size,
        overlap=settings.rag_chunk_overlap,
    )
    estimated_tokens = sum(estimate_tokens(chunk) for chunk in chunks)
    assert_token_budget(user, estimated_tokens)
    try:
        embedding_batch = provider.embed(chunks, task_type="document")
        if len(embedding_batch.vectors) != len(chunks):
            raise RuntimeError("El proveedor devolvió una cantidad inesperada de embeddings")
        if any(
            len(vector) != settings.ai_embedding_dimensions
            for vector in embedding_batch.vectors
        ):
            raise RuntimeError("La dimensión del embedding no coincide con la base vectorial")
        if document is None:
            document = Document(
                title=title,
                source_type="manual",
                source_url=source_url,
                content_hash=content_hash,
            )
            db.add(document)
            db.flush()
        else:
            document.title = title
            document.source_url = source_url
            document.content_hash = content_hash
            document.is_active = True
            document.chunks.clear()
            db.flush()
        document.chunks = [
            DocumentChunk(
                chunk_index=index,
                content=chunk,
                token_count=estimate_tokens(chunk),
                chunk_metadata={"title": title, "source_type": "manual"},
                embedding=vector,
            )
            for index, (chunk, vector) in enumerate(
                zip(chunks, embedding_batch.vectors, strict=True)
            )
        ]
        register_token_usage(user, embedding_batch.input_tokens)
        db.add(
            ServiceExecution(
                user_id=user.id,
                service_id=service_id,
                prompt_tokens=embedding_batch.input_tokens,
                completion_tokens=0,
                model_name=settings.ai_embedding_model,
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="success",
            )
        )
        db.commit()
        return IndexResult(document.id, len(chunks), embedding_batch.input_tokens, False)
    except Exception as exc:
        record_failed_execution(
            db,
            user_id=user.id,
            service_id=service_id,
            error=exc,
            duration_ms=round((time.perf_counter() - started) * 1000),
            model_name=settings.ai_embedding_model,
        )
        raise


def mark_book_index_stale(db: Session, book_id: uuid.UUID) -> None:
    """Excluye documentos antiguos hasta que el libro vuelva a indexarse."""
    documents = db.scalars(select(Document).where(Document.book_id == book_id)).all()
    for document in documents:
        document.is_active = False


def list_book_index_states(db: Session) -> list[BookIndexState]:
    """Compara el catálogo con sus documentos y detecta contenido desactualizado."""
    books = db.scalars(
        select(Book)
        .options(selectinload(Book.documents).selectinload(Document.chunks))
        .order_by(Book.title)
    ).all()
    states = []
    for book in books:
        document = next(
            (item for item in book.documents if item.source_type == "book_catalog"),
            None,
        )
        expected_hash = hashlib.sha256(build_book_document(book).encode("utf-8")).hexdigest()
        if not book.is_active:
            state = "inactive"
        elif document is None:
            state = "not_indexed"
        elif (
            document.is_active
            and document.content_hash == expected_hash
            and document.chunks
        ):
            state = "current"
        else:
            state = "stale"
        states.append(
            BookIndexState(
                book_id=book.id,
                title=book.title,
                status=state,
                document_id=document.id if document else None,
                chunks_indexed=len(document.chunks) if document else 0,
            )
        )
    return states


def retrieve_sources(
    db: Session,
    *,
    query_vector: list[float],
    top_k: int,
    max_distance: float = 0.75,
) -> list[tuple[DocumentChunk, Document, float]]:
    """Busca los fragmentos activos más cercanos por distancia coseno."""
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
    statement = (
        select(DocumentChunk, Document, distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.is_active.is_(True))
        .order_by(distance)
        .limit(top_k)
    )
    return [
        (chunk, document, float(score))
        for chunk, document, score in db.execute(statement).all()
        if float(score) <= max_distance
    ]


def get_conversation(
    db: Session,
    *,
    conversation_id: uuid.UUID | None,
    user: User,
    service: AiService,
    question: str,
) -> Conversation:
    """Recupera una conversación propia o inicia una nueva."""
    if conversation_id is None:
        conversation = Conversation(
            user_id=user.id,
            service_id=service.id,
            title=question[:197] + "..." if len(question) > 200 else question,
        )
        db.add(conversation)
        db.flush()
        return conversation

    statement = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conversation = db.scalar(statement)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="La conversación pertenece a otro usuario")
    if conversation.service_id != service.id:
        raise HTTPException(status_code=409, detail="La conversación pertenece a otro servicio")
    return conversation


def answer_question(
    db: Session,
    *,
    user: User,
    question: str,
    conversation_id: uuid.UUID | None,
    top_k: int,
    provider: AiProvider,
    settings: Settings,
) -> AnswerResult:
    """Ejecuta el ciclo RAG completo y persiste memoria, fuentes y consumo."""
    started = time.perf_counter()
    service = get_rag_service(db)
    assert_token_budget(user, service.max_tokens_per_request)
    conversation = get_conversation(
        db,
        conversation_id=conversation_id,
        user=user,
        service=service,
        question=question,
    )
    previous_messages = sorted(conversation.messages, key=lambda item: item.created_at)[-6:]

    try:
        question_embedding = provider.embed([question], task_type="query")
        matches = retrieve_sources(
            db,
            query_vector=question_embedding.vectors[0],
            top_k=top_k,
        )
        sources = [
            RetrievedSource(
                document_id=document.id,
                chunk_id=chunk.id,
                book_id=document.book_id,
                title=document.title,
                source_url=document.source_url,
                distance=distance,
            )
            for chunk, document, distance in matches
        ]

        generation_input_tokens = 0
        completion_tokens = 0
        if matches:
            prompt = build_rag_input(
                question=question,
                chunks=[
                    PromptChunk(title=document.title, content=chunk.content)
                    for chunk, document, _ in matches
                ],
                history=[(message.role, message.content) for message in previous_messages],
            )
            identifier = hashlib.sha256(str(user.id).encode("utf-8")).hexdigest()
            generation = provider.generate(
                instructions=RAG_INSTRUCTIONS,
                input_text=prompt,
                max_output_tokens=min(800, service.max_tokens_per_request),
                safety_identifier=identifier,
            )
            answer = generation.text
            generation_input_tokens = generation.input_tokens
            completion_tokens = generation.output_tokens
        else:
            answer = (
                "No encontré información suficiente en el catálogo para responder esa pregunta. "
                "Prueba con otro título, autor o género."
            )

        prompt_tokens = question_embedding.input_tokens + generation_input_tokens
        source_payload = [
            {
                "document_id": str(source.document_id),
                "chunk_id": str(source.chunk_id),
                "book_id": str(source.book_id) if source.book_id else None,
                "title": source.title,
                "source_url": source.source_url,
                "distance": round(source.distance, 6),
            }
            for source in sources
        ]
        conversation.messages.extend(
            [
                Message(role="user", content=question),
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
                model_name=settings.ai_chat_model,
                duration_ms=round((time.perf_counter() - started) * 1000),
                status="success",
            )
        )
        register_token_usage(user, prompt_tokens + completion_tokens)
        db.commit()
        return AnswerResult(
            conversation_id=conversation.id,
            answer=answer,
            sources=sources,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
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
            model_name=settings.ai_chat_model,
        )
        raise
