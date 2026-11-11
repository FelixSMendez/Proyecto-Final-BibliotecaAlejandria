"""CRUD protegido del catálogo de libros y sus clasificaciones."""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.models import Author, Book, BookAuthor, BookGenre, Genre, Publisher
from app.rag.service import mark_book_index_stale
from app.repositories.catalog import get_book, list_books
from app.schemas.catalog import (
    AuthorCreate,
    AuthorRead,
    BookCreate,
    BookRead,
    BookUpdate,
    GenreCreate,
    GenreRead,
    PublisherCreate,
    PublisherRead,
    book_to_read,
)

router = APIRouter(prefix="/catalog", tags=["Catálogo"])


def commit_or_conflict(db: DbSession, detail: str) -> None:
    """Confirma la transacción o traduce una restricción a HTTP 409."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


@router.get("/authors", response_model=list[AuthorRead])
def list_authors(db: DbSession, _: CurrentUser) -> list[Author]:
    """Lista autores en orden alfabético."""
    return list(db.scalars(select(Author).order_by(Author.full_name)).all())


@router.post("/authors", response_model=AuthorRead, status_code=status.HTTP_201_CREATED)
def create_author(payload: AuthorCreate, db: DbSession, _: AdminUser) -> Author:
    """Registra un autor con datos biográficos validados."""
    author = Author(**payload.model_dump())
    if author.country_code:
        author.country_code = author.country_code.upper()
    db.add(author)
    commit_or_conflict(db, "No fue posible crear el autor")
    db.refresh(author)
    return author


@router.put("/authors/{author_id}", response_model=AuthorRead)
def update_author(
    author_id: uuid.UUID, payload: AuthorCreate, db: DbSession, _: AdminUser
) -> Author:
    """Reemplaza los datos editables de un autor existente."""
    author = db.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    for field, value in payload.model_dump().items():
        setattr(author, field, value)
    if author.country_code:
        author.country_code = author.country_code.upper()
    for link in author.book_links:
        mark_book_index_stale(db, link.book_id)
    commit_or_conflict(db, "No fue posible actualizar el autor")
    db.refresh(author)
    return author


@router.delete("/authors/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: uuid.UUID, db: DbSession, _: AdminUser) -> None:
    """Elimina un autor únicamente si no tiene libros asociados."""
    author = db.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Autor no encontrado")
    db.delete(author)
    commit_or_conflict(db, "El autor está asociado a uno o más libros")


@router.get("/genres", response_model=list[GenreRead])
def list_genres(db: DbSession, _: CurrentUser) -> list[Genre]:
    """Lista géneros y categorías del catálogo."""
    return list(db.scalars(select(Genre).order_by(Genre.name)).all())


@router.post("/genres", response_model=GenreRead, status_code=status.HTTP_201_CREATED)
def create_genre(payload: GenreCreate, db: DbSession, _: AdminUser) -> Genre:
    """Crea un género y valida su categoría padre opcional."""
    if payload.parent_id is not None and db.get(Genre, payload.parent_id) is None:
        raise HTTPException(status_code=422, detail="El género padre no existe")
    genre = Genre(**payload.model_dump())
    db.add(genre)
    commit_or_conflict(db, "El género ya existe o sus datos son inválidos")
    db.refresh(genre)
    return genre


@router.put("/genres/{genre_id}", response_model=GenreRead)
def update_genre(
    genre_id: int, payload: GenreCreate, db: DbSession, _: AdminUser
) -> Genre:
    """Actualiza un género evitando referencias jerárquicas directas inválidas."""
    genre = db.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status_code=404, detail="Género no encontrado")
    if payload.parent_id == genre_id:
        raise HTTPException(status_code=422, detail="Un género no puede ser su propio padre")
    if payload.parent_id is not None and db.get(Genre, payload.parent_id) is None:
        raise HTTPException(status_code=422, detail="El género padre no existe")
    for field, value in payload.model_dump().items():
        setattr(genre, field, value)
    for link in genre.book_links:
        mark_book_index_stale(db, link.book_id)
    commit_or_conflict(db, "No fue posible actualizar el género")
    db.refresh(genre)
    return genre


@router.delete("/genres/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_genre(genre_id: int, db: DbSession, _: AdminUser) -> None:
    """Elimina un género que no esté utilizado por libros."""
    genre = db.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status_code=404, detail="Género no encontrado")
    db.delete(genre)
    commit_or_conflict(db, "El género está asociado a uno o más libros")


@router.get("/publishers", response_model=list[PublisherRead])
def list_publishers(db: DbSession, _: CurrentUser) -> list[Publisher]:
    """Lista editoriales en orden alfabético."""
    return list(db.scalars(select(Publisher).order_by(Publisher.name)).all())


@router.post("/publishers", response_model=PublisherRead, status_code=status.HTTP_201_CREATED)
def create_publisher(payload: PublisherCreate, db: DbSession, _: AdminUser) -> Publisher:
    """Registra una editorial normalizando su código de país."""
    data = payload.model_dump(mode="json")
    publisher = Publisher(**data)
    if publisher.country_code:
        publisher.country_code = publisher.country_code.upper()
    db.add(publisher)
    commit_or_conflict(db, "La editorial ya existe o sus datos son inválidos")
    db.refresh(publisher)
    return publisher


@router.put("/publishers/{publisher_id}", response_model=PublisherRead)
def update_publisher(
    publisher_id: uuid.UUID,
    payload: PublisherCreate,
    db: DbSession,
    _: AdminUser,
) -> Publisher:
    """Reemplaza la información editable de una editorial."""
    publisher = db.get(Publisher, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="Editorial no encontrada")
    for field, value in payload.model_dump(mode="json").items():
        setattr(publisher, field, value)
    if publisher.country_code:
        publisher.country_code = publisher.country_code.upper()
    for book in publisher.books:
        mark_book_index_stale(db, book.id)
    commit_or_conflict(db, "No fue posible actualizar la editorial")
    db.refresh(publisher)
    return publisher


@router.delete("/publishers/{publisher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publisher(publisher_id: uuid.UUID, db: DbSession, _: AdminUser) -> None:
    """Elimina una editorial y conserva sus libros sin asociación."""
    publisher = db.get(Publisher, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="Editorial no encontrada")
    for book in publisher.books:
        mark_book_index_stale(db, book.id)
    db.delete(publisher)
    commit_or_conflict(db, "No fue posible eliminar la editorial")


def validate_book_relationships(
    db: DbSession,
    *,
    author_ids: list[uuid.UUID],
    genre_ids: list[int],
    publisher_id: uuid.UUID | None,
) -> None:
    """Comprueba que autores, géneros y editorial existan antes de guardar."""
    found_authors = set(db.scalars(select(Author.id).where(Author.id.in_(author_ids))).all())
    if found_authors != set(author_ids):
        raise HTTPException(status_code=422, detail="Uno o más autores no existen")
    if genre_ids:
        found_genres = set(db.scalars(select(Genre.id).where(Genre.id.in_(genre_ids))).all())
        if found_genres != set(genre_ids):
            raise HTTPException(status_code=422, detail="Uno o más géneros no existen")
    if publisher_id is not None and db.get(Publisher, publisher_id) is None:
        raise HTTPException(status_code=422, detail="La editorial no existe")


@router.get("/books", response_model=list[BookRead])
def read_books(
    db: DbSession,
    _: CurrentUser,
    search: str | None = Query(default=None, max_length=150),
    active_only: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[BookRead]:
    """Busca libros activos con paginación y relaciones incluidas."""
    books = list_books(
        db, search=search, active_only=active_only, offset=offset, limit=limit
    )
    return [book_to_read(book) for book in books]


@router.get("/books/{book_id}", response_model=BookRead)
def read_book(book_id: uuid.UUID, db: DbSession, _: CurrentUser) -> BookRead:
    """Obtiene el detalle completo de un libro."""
    book = get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return book_to_read(book)


@router.post("/books", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def create_book(payload: BookCreate, db: DbSession, _: AdminUser) -> BookRead:
    """Crea un libro y sus asociaciones en una transacción."""
    validate_book_relationships(
        db,
        author_ids=payload.author_ids,
        genre_ids=payload.genre_ids,
        publisher_id=payload.publisher_id,
    )
    data = payload.model_dump(
        mode="json", exclude={"author_ids", "genre_ids", "cover_url", "source_url"}
    )
    data["cover_url"] = str(payload.cover_url) if payload.cover_url else None
    data["source_url"] = str(payload.source_url) if payload.source_url else None
    book = Book(**data)
    book.author_links = [
        BookAuthor(author_id=author_id, author_order=index)
        for index, author_id in enumerate(dict.fromkeys(payload.author_ids), start=1)
    ]
    book.genre_links = [
        BookGenre(genre_id=genre_id) for genre_id in dict.fromkeys(payload.genre_ids)
    ]
    db.add(book)
    commit_or_conflict(db, "El ISBN ya existe o los datos del libro son inválidos")
    return book_to_read(get_book(db, book.id))


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(
    book_id: uuid.UUID,
    payload: BookUpdate,
    db: DbSession,
    _: AdminUser,
) -> BookRead:
    """Aplica cambios parciales y sincroniza autores y géneros."""
    book = get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")

    author_ids = payload.author_ids if payload.author_ids is not None else [
        link.author_id for link in book.author_links
    ]
    genre_ids = payload.genre_ids if payload.genre_ids is not None else [
        link.genre_id for link in book.genre_links
    ]
    publisher_id = (
        payload.publisher_id if "publisher_id" in payload.model_fields_set else book.publisher_id
    )
    validate_book_relationships(
        db, author_ids=author_ids, genre_ids=genre_ids, publisher_id=publisher_id
    )

    data = payload.model_dump(
        mode="json",
        exclude_unset=True,
        exclude={"author_ids", "genre_ids", "cover_url", "source_url"},
    )
    for field, value in data.items():
        setattr(book, field, value)
    if "cover_url" in payload.model_fields_set:
        book.cover_url = str(payload.cover_url) if payload.cover_url else None
    if "source_url" in payload.model_fields_set:
        book.source_url = str(payload.source_url) if payload.source_url else None
    if payload.author_ids is not None:
        book.author_links = [
            BookAuthor(author_id=author_id, author_order=index)
            for index, author_id in enumerate(dict.fromkeys(payload.author_ids), start=1)
        ]
    if payload.genre_ids is not None:
        book.genre_links = [
            BookGenre(genre_id=genre_id) for genre_id in dict.fromkeys(payload.genre_ids)
        ]

    mark_book_index_stale(db, book.id)
    commit_or_conflict(db, "El ISBN ya existe o los datos del libro son inválidos")
    return book_to_read(get_book(db, book.id))


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_book(book_id: uuid.UUID, db: DbSession, _: AdminUser) -> None:
    """Retira un libro del catálogo mediante borrado lógico."""
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    book.is_active = False
    mark_book_index_stale(db, book.id)
    db.commit()
