"""Funciones criptográficas para contraseñas y tokens de sesión."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import get_settings

# Argon2 protege cuentas nuevas; bcrypt mantiene compatibilidad con las semillas SQL.
password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def hash_password(password: str) -> str:
    """Genera un hash Argon2 para una contraseña nueva."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Valida contraseñas Argon2 o bcrypt sin exponer el hash."""
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, role: str) -> str:
    """Emite un JWT de acceso corto con identidad y rol."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Valida la firma, expiración y tipo de un access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise ValueError("Token inválido o vencido") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise ValueError("Token de acceso inválido")
    return payload


def generate_refresh_token() -> str:
    """Crea un refresh token criptográficamente aleatorio."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Reduce el refresh token a un identificador seguro para persistencia."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
