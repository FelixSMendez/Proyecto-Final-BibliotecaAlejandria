"""Contratos de entrada y salida para usuarios."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Datos requeridos para registrar una cuenta."""

    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role_code: str = Field(default="user", pattern="^(admin|user)$")
    monthly_token_limit: int = Field(default=100000, ge=0)


class UserUpdate(BaseModel):
    """Cambios parciales permitidos sobre una cuenta."""

    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role_code: str | None = Field(default=None, pattern="^(admin|user)$")
    is_active: bool | None = None
    monthly_token_limit: int | None = Field(default=None, ge=0)


class UserRead(BaseModel):
    """Representación pública y administrativa de un usuario."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    monthly_token_limit: int
    monthly_tokens_used: int
    token_period_start: date
    role_code: str
    last_login_at: datetime | None
    created_at: datetime


def user_to_read(user: object) -> UserRead:
    """Convierte una entidad cargada a su representación pública."""
    return UserRead(
        id=user.id,
        email=str(user.email),
        display_name=user.display_name,
        is_active=user.is_active,
        monthly_token_limit=user.monthly_token_limit,
        monthly_tokens_used=user.monthly_tokens_used,
        token_period_start=user.token_period_start,
        role_code=user.role.code,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )
