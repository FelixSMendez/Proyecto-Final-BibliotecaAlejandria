"""Consultas optimizadas para cargar y buscar el catálogo."""

import uuid

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Book, BookAuthor, BookGenre


def book_load_options() -> tuple:
    """Define carga anticipada para evitar consultas N+1."""
    return (
        selectinload(Book.publisher),
        selectinload(Book.author_links).selectinload(BookAuthor.author),
        selectinload(Book.genre_links).selectinload(BookGenre.genre),
    )


def get_book(db: Session, book_id: uuid.UUID) -> Book | None:
    """Recupera un libro con editorial, autores y géneros."""
    statement = select(Book).options(*book_load_options()).where(Book.id == book_id)
    return db.scalar(statement)


def list_books_statement(
    *, search: str | None, active_only: bool, offset: int, limit: int
) -> Select[tuple[Book]]:
    """Construye la consulta paginada y filtrable del catálogo."""
    statement = select(Book).options(*book_load_options()).order_by(Book.title)
    if active_only:
        statement = statement.where(Book.is_active.is_(True))
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Book.title.ilike(pattern),
                Book.subtitle.ilike(pattern),
                Book.synopsis.ilike(pattern),
            )
        )
    return statement.offset(offset).limit(limit)


def list_books(
    db: Session, *, search: str | None, active_only: bool, offset: int, limit: int
) -> list[Book]:
    """Ejecuta la consulta del catálogo y materializa sus resultados."""
    return list(db.scalars(list_books_statement(
        search=search, active_only=active_only, offset=offset, limit=limit
    )).all())
