"""Registra el modelo utilizado por cada ejecución.

Revision ID: 0004_execution_model
Revises: 0003_external_sources
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_execution_model"
down_revision: str | None = "0003_external_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega el identificador auditable del modelo de IA."""
    op.add_column("service_executions", sa.Column("model_name", sa.String(250)))


def downgrade() -> None:
    """Retira el identificador de modelo de las ejecuciones."""
    op.drop_column("service_executions", "model_name")
