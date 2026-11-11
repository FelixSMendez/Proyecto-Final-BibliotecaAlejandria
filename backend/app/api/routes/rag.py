"""Endpoints para indexar el catálogo y consultar el bibliotecario RAG."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.core.config import get_settings
from app.models import Document
from app.rag.providers import (
    AiProviderConfigurationError,
    AiProviderUnavailableError,
    get_ai_provider,
)
from app.rag.service import (
    answer_question,
    index_book,
    index_books_batch,
    index_manual_document,
    list_book_index_states,
)
from app.repositories.catalog import get_book
from app.schemas.rag import (
    BookIndexResponse,
    BookIndexStatus,
    BulkIndexItem,
    BulkIndexResponse,
    ManualDocumentRead,
    ManualDocumentWrite,
    RagChatRequest,
    RagChatResponse,
    RagSourceRead,
    RagTokenUsage,
)

router = APIRouter(tags=["Bibliotecario RAG"])


def provider_or_503():
    """Construye el proveedor o traduce una configuración incompleta."""
    try:
        return get_ai_provider()
    except AiProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def manual_document_or_404(db: DbSession, document_id: uuid.UUID) -> Document:
    """Recupera un documento manual con sus fragmentos."""
    statement = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.id == document_id, Document.source_type == "manual")
    )
    document = db.scalar(statement)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento interno no encontrado")
    return document


@router.get("/rag/documents", response_model=list[ManualDocumentRead])
def list_manual_documents(db: DbSession, _: AdminUser) -> list[ManualDocumentRead]:
    """Lista documentos internos y cantidad de fragmentos."""
    documents = db.scalars(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.source_type == "manual")
        .order_by(Document.title)
    ).all()
    return [
        ManualDocumentRead(
            id=document.id,
            title=document.title,
            source_url=document.source_url,
            is_active=document.is_active,
            chunks_indexed=len(document.chunks),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        for document in documents
    ]


def save_manual_document(
    db: DbSession,
    current_admin: AdminUser,
    payload: ManualDocumentWrite,
    document: Document | None = None,
) -> BookIndexResponse:
    """Indexa un texto interno y traduce errores del proveedor."""
    try:
        result = index_manual_document(
            db,
            title=payload.title.strip(),
            content=payload.content,
            source_url=str(payload.source_url) if payload.source_url else None,
            user=current_admin,
            provider=provider_or_503(),
            settings=get_settings(),
            document=document,
        )
    except HTTPException:
        raise
    except AiProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini está temporalmente saturado; intenta nuevamente en unos segundos",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible indexar el documento interno",
        ) from exc
    return BookIndexResponse(**result.__dict__)


@router.post(
    "/rag/documents",
    response_model=BookIndexResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_document(
    payload: ManualDocumentWrite,
    db: DbSession,
    current_admin: AdminUser,
) -> BookIndexResponse:
    """Crea e indexa un documento interno administrable."""
    return save_manual_document(db, current_admin, payload)


@router.put("/rag/documents/{document_id}", response_model=BookIndexResponse)
def update_manual_document(
    document_id: uuid.UUID,
    payload: ManualDocumentWrite,
    db: DbSession,
    current_admin: AdminUser,
) -> BookIndexResponse:
    """Reemplaza el texto y regenera sus fragmentos cuando cambió."""
    document = manual_document_or_404(db, document_id)
    return save_manual_document(db, current_admin, payload, document)


@router.delete("/rag/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_manual_document(
    document_id: uuid.UUID,
    db: DbSession,
    _: AdminUser,
) -> None:
    """Retira un documento interno de futuras recuperaciones."""
    document = manual_document_or_404(db, document_id)
    document.is_active = False
    db.commit()


@router.get("/rag/books/status", response_model=list[BookIndexStatus])
def read_index_status(db: DbSession, _: AdminUser) -> list[BookIndexStatus]:
    """Lista libros actuales, pendientes, desactualizados o inactivos."""
    return [BookIndexStatus(**item.__dict__) for item in list_book_index_states(db)]


@router.post("/rag/books/index-all", response_model=BulkIndexResponse)
def index_entire_catalog(
    db: DbSession,
    current_admin: AdminUser,
) -> BulkIndexResponse:
    """Indexa libros activos y conserva los fallos por elemento."""
    settings = get_settings()
    provider = provider_or_503()
    states = [
        item
        for item in list_book_index_states(db)
        if item.status in {"not_indexed", "stale"}
    ]
    items: list[BulkIndexItem] = []
    batch_size = settings.rag_index_batch_size
    for start in range(0, len(states), batch_size):
        batch_states = states[start : start + batch_size]
        books = [book for item in batch_states if (book := get_book(db, item.book_id))]
        if not books:
            continue
        try:
            results = index_books_batch(
                db,
                books=books,
                user=current_admin,
                provider=provider,
                settings=settings,
            )
            items.extend(
                [
                    BulkIndexItem(
                        book_id=book.id,
                        title=book.title,
                        status="unchanged" if results[book.id].unchanged else "indexed",
                        chunks_indexed=results[book.id].chunks_indexed,
                    )
                    for book in books
                ]
            )
        except AiProviderUnavailableError as exc:
            remaining_states = states[start:]
            items.extend(
                BulkIndexItem(
                    book_id=item.book_id,
                    title=item.title,
                    status="failed",
                    error=str(exc),
                )
                for item in remaining_states
            )
            break
        except Exception as exc:
            items.extend(
                BulkIndexItem(
                    book_id=book.id,
                    title=book.title,
                    status="failed",
                    error=str(exc)[:300],
                )
                for book in books
            )
    return BulkIndexResponse(
        total=len(items),
        indexed=sum(item.status == "indexed" for item in items),
        unchanged=sum(item.status == "unchanged" for item in items),
        failed=sum(item.status == "failed" for item in items),
        items=items,
    )


@router.post(
    "/rag/books/{book_id}/index",
    response_model=BookIndexResponse,
    responses={
        502: {"description": "El proveedor rechazó la generación de embeddings"},
        503: {"description": "Proveedor no configurado o temporalmente no disponible"},
    },
)
def index_catalog_book(
    book_id: uuid.UUID,
    db: DbSession,
    current_admin: AdminUser,
) -> BookIndexResponse:
    """Genera embeddings del libro seleccionado para búsqueda semántica."""
    book = get_book(db, book_id)
    if book is None or not book.is_active:
        raise HTTPException(status_code=404, detail="Libro activo no encontrado")
    provider = provider_or_503()
    try:
        result = index_book(
            db,
            book=book,
            user=current_admin,
            provider=provider,
            settings=get_settings(),
        )
    except HTTPException:
        raise
    except AiProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini está temporalmente saturado; intenta nuevamente en unos segundos",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible generar los embeddings del libro",
        ) from exc
    return BookIndexResponse(**result.__dict__)


@router.post(
    "/ai/chat",
    response_model=RagChatResponse,
    responses={
        502: {"description": "El proveedor rechazó la solicitud"},
        503: {"description": "Proveedor no configurado o temporalmente no disponible"},
    },
)
def chat_with_librarian(
    payload: RagChatRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RagChatResponse:
    """Responde con RAG y conserva memoria, fuentes y consumo."""
    settings = get_settings()
    provider = provider_or_503()
    try:
        result = answer_question(
            db,
            user=current_user,
            question=payload.question.strip(),
            conversation_id=payload.conversation_id,
            top_k=payload.top_k or settings.rag_top_k,
            provider=provider,
            settings=settings,
        )
    except HTTPException:
        raise
    except AiProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini está temporalmente saturado; intenta nuevamente en unos segundos",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El proveedor de IA no pudo completar la solicitud",
        ) from exc

    return RagChatResponse(
        conversation_id=result.conversation_id,
        answer=result.answer,
        sources=[RagSourceRead(**source.__dict__) for source in result.sources],
        usage=RagTokenUsage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
        ),
    )
