"""Consultas ORM para usuarios y roles."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Role, User


def get_user_by_email(db: Session, email: str) -> User | None:
    """Busca un usuario por correo e incluye su rol."""
    statement = select(User).options(selectinload(User.role)).where(User.email == email)
    return db.scalar(statement)


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Recupera un usuario por UUID e incluye su rol."""
    statement = select(User).options(selectinload(User.role)).where(User.id == user_id)
    return db.scalar(statement)


def get_role_by_code(db: Session, code: str) -> Role | None:
    """Obtiene un rol por su código estable."""
    return db.scalar(select(Role).where(Role.code == code))
