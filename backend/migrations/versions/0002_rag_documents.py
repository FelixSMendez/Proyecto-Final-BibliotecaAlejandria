"""Agrega documentos y fragmentos vectoriales para RAG.

Revision ID: 0002_rag_documents
Revises: 0001_ai_history
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0002_rag_documents"
down_revision: str | None = "0001_ai_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea fuentes documentales, fragmentos e índice de similitud."""
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "book_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
        ),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "source_type IN ('book_catalog', 'manual', 'external')",
            name="documents_source_type_allowed",
        ),
        sa.UniqueConstraint("book_id", "source_type", name="documents_book_source_unique"),
    )
    op.create_index("idx_documents_book", "documents", ["book_id"])
    op.create_index(
        "idx_documents_active",
        "documents",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("chunk_index >= 0", name="document_chunks_index_nonnegative"),
        sa.CheckConstraint("token_count >= 0", name="document_chunks_tokens_nonnegative"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="document_chunks_position_unique"
        ),
    )
    op.create_index("idx_document_chunks_document", "document_chunks", ["document_id"])

    # HNSW acelera la distancia coseno sin requerir entrenamiento previo del índice.
    op.execute(
        "CREATE INDEX idx_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Elimina el índice vectorial y las fuentes RAG."""
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_embedding_hnsw")
    op.drop_index("idx_document_chunks_document", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("idx_documents_active", table_name="documents")
    op.drop_index("idx_documents_book", table_name="documents")
    op.drop_table("documents")
