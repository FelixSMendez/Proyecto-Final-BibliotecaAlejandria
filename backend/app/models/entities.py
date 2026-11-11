"""Entidades SQLAlchemy de seguridad, catálogo y actividad de IA."""

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import CITEXT, INET, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    """Añade marcas de creación y modificación a entidades mutables."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Role(Base):
    """Rol estable usado para autorización de usuarios."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(TimestampMixin, Base):
    """Cuenta autenticable con rol y cuota mensual de tokens."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    monthly_token_limit: Mapped[int] = mapped_column(Integer, default=100000, nullable=False)
    monthly_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship(back_populates="users")
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    service_executions: Mapped[list["ServiceExecution"]] = relationship(
        back_populates="user"
    )


class UserSession(Base):
    """Sesión revocable identificada por el hash del refresh token."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class Publisher(TimestampMixin, Base):
    """Editorial asociada opcionalmente a múltiples libros."""

    __tablename__ = "publishers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    website_url: Mapped[str | None] = mapped_column(Text)

    books: Mapped[list["Book"]] = relationship(back_populates="publisher")


class Author(TimestampMixin, Base):
    """Autor o colaborador bibliográfico con identidad externa opcional."""

    __tablename__ = "authors"
    __table_args__ = (
        UniqueConstraint("external_source", "external_id", name="authors_external_identity_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    biography: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)
    death_date: Mapped[date | None] = mapped_column(Date)
    country_code: Mapped[str | None] = mapped_column(String(2))
    external_source: Mapped[str | None] = mapped_column(String(50))
    external_id: Mapped[str | None] = mapped_column(String(150))

    book_links: Mapped[list["BookAuthor"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )


class Genre(Base):
    """Clasificación jerárquica para filtrar el catálogo."""

    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("genres.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    parent: Mapped["Genre | None"] = relationship(remote_side=[id])
    book_links: Mapped[list["BookGenre"]] = relationship(
        back_populates="genre", cascade="all, delete-orphan"
    )


class Book(TimestampMixin, Base):
    """Obra bibliográfica con metadatos y búsqueda textual generada."""

    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint("external_source", "external_id", name="books_external_identity_unique"),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="books_page_count_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publisher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publishers.id", ondelete="SET NULL")
    )
    isbn_10: Mapped[str | None] = mapped_column(String(10), unique=True)
    isbn_13: Mapped[str | None] = mapped_column(String(13), unique=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(250))
    synopsis: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(SmallInteger)
    language_code: Mapped[str] = mapped_column(String(10), default="es", nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    cover_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    external_source: Mapped[str | None] = mapped_column(String(50))
    external_id: Mapped[str | None] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', "
            "coalesce(title, '') || ' ' || coalesce(subtitle, '') || ' ' || "
            "coalesce(synopsis, ''))",
            persisted=True,
        ),
    )

    publisher: Mapped[Publisher | None] = relationship(back_populates="books")
    author_links: Mapped[list["BookAuthor"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    genre_links: Mapped[list["BookGenre"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )


class BookAuthor(Base):
    """Asociación ordenada entre una obra y sus colaboradores."""

    __tablename__ = "book_authors"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authors.id", ondelete="RESTRICT"), primary_key=True
    )
    author_order: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    contribution: Mapped[str] = mapped_column(
        String(40), primary_key=True, default="author", nullable=False
    )

    book: Mapped[Book] = relationship(back_populates="author_links")
    author: Mapped[Author] = relationship(back_populates="book_links")


class BookGenre(Base):
    """Asociación muchos-a-muchos entre libros y géneros."""

    __tablename__ = "book_genres"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(
        ForeignKey("genres.id", ondelete="RESTRICT"), primary_key=True
    )

    book: Mapped[Book] = relationship(back_populates="genre_links")
    genre: Mapped[Genre] = relationship(back_populates="book_links")


class AiService(TimestampMixin, Base):
    """Configuración administrable de un servicio de inteligencia artificial."""

    __tablename__ = "ai_services"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_tokens_per_request: Mapped[int] = mapped_column(Integer, default=4000, nullable=False)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="service")
    executions: Mapped[list["ServiceExecution"]] = relationship(back_populates="service")


class Conversation(TimestampMixin, Base):
    """Agrupa mensajes y ejecuciones de un usuario y servicio."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("ai_services.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    user: Mapped[User] = relationship(back_populates="conversations")
    service: Mapped[AiService] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    external_sources: Mapped[list["ExternalSource"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    executions: Mapped[list["ServiceExecution"]] = relationship(
        back_populates="conversation"
    )


class Message(Base):
    """Mensaje conversacional con fuentes y consumo atribuido."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list[dict]] = mapped_column(postgresql.JSONB, default=list, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ServiceExecution(Base):
    """Audita una solicitud de IA, resultado, duración y tokens."""

    __tablename__ = "service_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("ai_services.id", ondelete="RESTRICT"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(250))
    total_tokens: Mapped[int] = mapped_column(
        Integer, Computed("prompt_tokens + completion_tokens", persisted=True)
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="service_executions")
    service: Mapped[AiService] = relationship(back_populates="executions")
    conversation: Mapped[Conversation | None] = relationship(back_populates="executions")


class ExternalSource(Base):
    """Fuente externa consultada durante una investigación literaria."""

    __tablename__ = "external_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(180))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(
        "metadata", postgresql.JSONB, default=dict, nullable=False
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="external_sources")


class Document(TimestampMixin, Base):
    """Fuente normalizada que alimenta la recuperación semántica."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    book: Mapped[Book | None] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """Fragmento de texto con embedding y metadatos de procedencia."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(
        "metadata", postgresql.JSONB, default=dict, nullable=False
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
