"""Reglas de autenticación, bloqueo y administración de sesiones."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models import User, UserSession
from app.repositories.users import get_user_by_email
from app.schemas.auth import TokenPair


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Valida credenciales y aplica bloqueo temporal por intentos fallidos."""
    user = get_user_by_email(db, email)
    now = datetime.now(UTC)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada temporalmente",
        )
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
            user.failed_login_attempts = 0
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.flush()
    return user


def issue_token_pair(
    db: Session,
    user: User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenPair:
    """Emite access/refresh tokens y registra la sesión revocable."""
    settings = get_settings()
    refresh_token = generate_refresh_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    db.commit()

    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.code),
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


def rotate_refresh_token(
    db: Session,
    refresh_token: str,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenPair:
    """Revoca una sesión usada y entrega un par de tokens nuevo."""
    token_hash = hash_refresh_token(refresh_token)
    statement = (
        select(UserSession)
        .options(selectinload(UserSession.user).selectinload(User.role))
        .where(UserSession.refresh_token_hash == token_hash)
    )
    session = db.scalar(statement)
    now = datetime.now(UTC)
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or not session.user.is_active
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")

    session.revoked_at = now
    db.flush()
    return issue_token_pair(
        db,
        session.user,
        user_agent=user_agent,
        ip_address=ip_address,
    )


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Invalida la sesión asociada a un refresh token conocido."""
    token_hash = hash_refresh_token(refresh_token)
    session = db.scalar(
        select(UserSession).where(UserSession.refresh_token_hash == token_hash)
    )
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
