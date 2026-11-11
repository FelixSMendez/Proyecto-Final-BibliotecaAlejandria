"""CRUD administrativo de usuarios y límites de consumo."""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.dependencies import AdminUser, DbSession
from app.core.security import hash_password
from app.models import User
from app.repositories.users import get_role_by_code, get_user_by_email, get_user_by_id
from app.schemas.users import UserCreate, UserRead, UserUpdate, user_to_read

router = APIRouter(prefix="/users", tags=["Usuarios"])


@router.get("", response_model=list[UserRead])
def list_users(
    db: DbSession,
    _: AdminUser,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[UserRead]:
    """Lista usuarios de forma paginada para administración."""
    statement = (
        select(User).options(selectinload(User.role)).order_by(User.created_at.desc())
    )
    users = db.scalars(statement.offset(offset).limit(limit)).all()
    return [user_to_read(user) for user in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, _: AdminUser) -> UserRead:
    """Crea un usuario con contraseña protegida y rol válido."""
    if get_user_by_email(db, str(payload.email)):
        raise HTTPException(status_code=409, detail="El correo ya está registrado")
    role = get_role_by_code(db, payload.role_code)
    if role is None:
        raise HTTPException(status_code=422, detail="El rol solicitado no existe")

    today = date.today()
    user = User(
        role_id=role.id,
        email=str(payload.email),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        monthly_token_limit=payload.monthly_token_limit,
        token_period_start=today.replace(day=1),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No fue posible crear el usuario") from exc
    return user_to_read(get_user_by_id(db, user.id))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: DbSession,
    current_admin: AdminUser,
) -> UserRead:
    """Actualiza perfil, seguridad, rol o cuota del usuario."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    changes = payload.model_dump(exclude_unset=True, exclude={"password", "role_code"})
    for field, value in changes.items():
        setattr(user, field, value.strip() if field == "display_name" else value)
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.role_code is not None:
        role = get_role_by_code(db, payload.role_code)
        if role is None:
            raise HTTPException(status_code=422, detail="El rol solicitado no existe")
        if user.id == current_admin.id and role.code != "admin":
            raise HTTPException(
                status_code=400,
                detail="No puede retirar su propio rol administrador",
            )
        user.role_id = role.id

    db.commit()
    return user_to_read(get_user_by_id(db, user.id))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: uuid.UUID,
    db: DbSession,
    current_admin: AdminUser,
) -> None:
    """Desactiva lógicamente una cuenta y protege al administrador actual."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta")
    user.is_active = False
    db.commit()
