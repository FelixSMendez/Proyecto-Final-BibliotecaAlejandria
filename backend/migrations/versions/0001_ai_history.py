"""Agrega servicios de IA, historial y consumo de tokens.

Revision ID: 0001_ai_history
Revises:
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_ai_history"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea historial, servicios configurables y auditoría de consumo."""
    op.create_table(
        "ai_services",
        sa.Column("id", sa.SmallInteger(), sa.Identity(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("model_name", sa.String(120)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "max_tokens_per_request", sa.Integer(), nullable=False, server_default="4000"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "max_tokens_per_request > 0", name="ai_services_max_tokens_positive"
        ),
    )

    op.create_table(
        "conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            sa.SmallInteger(),
            sa.ForeignKey("ai_services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="conversations_status_allowed"
        ),
    )
    op.create_index("idx_conversations_user_created", "conversations", ["user_id", "created_at"])
    op.create_index("idx_conversations_service", "conversations", ["service_id"])

    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "sources",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "role IN ('system', 'user', 'assistant', 'tool')", name="messages_role_allowed"
        ),
        sa.CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0",
            name="messages_tokens_nonnegative",
        ),
    )
    op.create_index(
        "idx_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )

    op.create_table(
        "service_executions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            sa.SmallInteger(),
            sa.ForeignKey("ai_services.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
        ),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_tokens",
            sa.Integer(),
            sa.Computed("prompt_tokens + completion_tokens", persisted=True),
        ),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'blocked')", name="executions_status_allowed"
        ),
        sa.CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0",
            name="executions_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0", name="executions_duration_nonnegative"
        ),
    )
    op.create_index(
        "idx_executions_user_created", "service_executions", ["user_id", "created_at"]
    )
    op.create_index(
        "idx_executions_service_created", "service_executions", ["service_id", "created_at"]
    )

    services = sa.table(
        "ai_services",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        services,
        [
            {
                "code": "rag_librarian",
                "name": "Bibliotecario virtual",
                "description": "Responde con información recuperada del catálogo.",
            },
            {
                "code": "book_recommender",
                "name": "Recomendador de lecturas",
                "description": "Compara libros y genera recomendaciones razonadas.",
            },
            {
                "code": "literary_research",
                "name": "Investigación literaria",
                "description": "Investiga autores, obras y corrientes con fuentes.",
            },
        ],
    )


def downgrade() -> None:
    """Retira las tablas de actividad en orden seguro de dependencias."""
    op.drop_index("idx_executions_service_created", table_name="service_executions")
    op.drop_index("idx_executions_user_created", table_name="service_executions")
    op.drop_table("service_executions")
    op.drop_index("idx_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("idx_conversations_service", table_name="conversations")
    op.drop_index("idx_conversations_user_created", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("ai_services")
