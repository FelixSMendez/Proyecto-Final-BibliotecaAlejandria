"""Endpoints de inicio, renovación y cierre de sesión."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.auth import LogoutRequest, RefreshTokenRequest, TokenPair
from app.schemas.users import UserRead, user_to_read
from app.services.auth import (
    authenticate_user,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def client_ip(request: Request) -> str | None:
    """Extrae la IP observada para auditoría de la sesión."""
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenPair)
def login(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenPair:
    """Autentica credenciales OAuth2 y devuelve un par de tokens."""
    user = authenticate_user(db, form.username, form.password)
    return issue_token_pair(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(
    payload: RefreshTokenRequest,
    request: Request,
    db: DbSession,
) -> TokenPair:
    """Rota el refresh token y mantiene una única sesión válida."""
    return rotate_refresh_token(
        db,
        payload.refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: DbSession) -> Response:
    """Revoca la sesión sin revelar si el token ya era inválido."""
    revoke_refresh_token(db, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> UserRead:
    """Devuelve el perfil asociado al token actual."""
    return user_to_read(current_user)
