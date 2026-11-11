"""Validación y respuestas del dominio bibliográfico."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class AuthorCreate(BaseModel):
    """Datos biográficos editables de un autor."""

    full_name: str = Field(min_length=1, max_length=180)
    biography: str | None = None
    birth_date: date | None = None
    death_date: date | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_dates(self) -> "AuthorCreate":
        """Impide rangos biográficos cronológicamente inválidos."""
        if self.birth_date and self.death_date and self.death_date < self.birth_date:
            raise ValueError("La fecha de fallecimiento no puede preceder al nacimiento")
        return self


class AuthorRead(AuthorCreate):
    """Autor persistido con su identificador."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class GenreCreate(BaseModel):
    """Datos editables de un género jerárquico."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    parent_id: int | None = None


class GenreRead(GenreCreate):
    """Género persistido con su identificador."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class PublisherCreate(BaseModel):
    """Datos editables de una editorial."""

    name: str = Field(min_length=1, max_length=180)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    website_url: HttpUrl | None = None


class PublisherRead(BaseModel):
    """Representación pública de una editorial."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country_code: str | None
    website_url: str | None


class BookCreate(BaseModel):
    """Datos y relaciones requeridos para registrar un libro."""

    title: str = Field(min_length=1, max_length=250)
    subtitle: str | None = Field(default=None, max_length=250)
    synopsis: str | None = None
    isbn_10: str | None = Field(default=None, pattern=r"^[0-9]{9}[0-9X]$")
    isbn_13: str | None = Field(default=None, pattern=r"^[0-9]{13}$")
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    language_code: str = Field(default="es", min_length=2, max_length=10)
    page_count: int | None = Field(default=None, gt=0)
    cover_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    publisher_id: uuid.UUID | None = None
    author_ids: list[uuid.UUID] = Field(min_length=1)
    genre_ids: list[int] = Field(default_factory=list)


class BookUpdate(BaseModel):
    """Cambios parciales admitidos sobre un libro."""

    title: str | None = Field(default=None, min_length=1, max_length=250)
    subtitle: str | None = Field(default=None, max_length=250)
    synopsis: str | None = None
    isbn_10: str | None = Field(default=None, pattern=r"^[0-9]{9}[0-9X]$")
    isbn_13: str | None = Field(default=None, pattern=r"^[0-9]{13}$")
    publication_year: int | None = Field(default=None, ge=1000, le=2100)
    language_code: str | None = Field(default=None, min_length=2, max_length=10)
    page_count: int | None = Field(default=None, gt=0)
    cover_url: HttpUrl | None = None
    source_url: HttpUrl | None = None
    publisher_id: uuid.UUID | None = None
    author_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    genre_ids: list[int] | None = None
    is_active: bool | None = None


class AuthorSummary(BaseModel):
    """Autor resumido dentro de la respuesta de un libro."""

    id: uuid.UUID
    full_name: str
    contribution: str


class GenreSummary(BaseModel):
    """Género resumido dentro de la respuesta de un libro."""

    id: int
    name: str


class PublisherSummary(BaseModel):
    """Editorial resumida dentro de la respuesta de un libro."""

    id: uuid.UUID
    name: str


class BookRead(BaseModel):
    """Detalle completo de un libro expuesto por la API."""

    id: uuid.UUID
    title: str
    subtitle: str | None
    synopsis: str | None
    isbn_10: str | None
    isbn_13: str | None
    publication_year: int | None
    language_code: str
    page_count: int | None
    cover_url: str | None
    source_url: str | None
    is_active: bool
    publisher: PublisherSummary | None
    authors: list[AuthorSummary]
    genres: list[GenreSummary]
    created_at: datetime
    updated_at: datetime


def book_to_read(book: object) -> BookRead:
    """Proyecta un libro ORM y sus relaciones al contrato de API."""
    publisher = None
    if book.publisher:
        publisher = PublisherSummary(id=book.publisher.id, name=book.publisher.name)

    return BookRead(
        id=book.id,
        title=book.title,
        subtitle=book.subtitle,
        synopsis=book.synopsis,
        isbn_10=book.isbn_10,
        isbn_13=book.isbn_13,
        publication_year=book.publication_year,
        language_code=book.language_code,
        page_count=book.page_count,
        cover_url=book.cover_url,
        source_url=book.source_url,
        is_active=book.is_active,
        publisher=publisher,
        authors=[
            AuthorSummary(
                id=link.author.id,
                full_name=link.author.full_name,
                contribution=link.contribution,
            )
            for link in sorted(book.author_links, key=lambda item: item.author_order)
        ],
        genres=[
            GenreSummary(id=link.genre.id, name=link.genre.name) for link in book.genre_links
        ],
        created_at=book.created_at,
        updated_at=book.updated_at,
    )
