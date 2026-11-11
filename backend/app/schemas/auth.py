"""Contratos HTTP para emisión y revocación de tokens."""

from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    """Par de tokens y vigencia del access token."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Solicitud de rotación de una sesión existente."""

    refresh_token: str = Field(min_length=32)


class LogoutRequest(BaseModel):
    """Solicitud de revocación de una sesión."""

    refresh_token: str = Field(min_length=32)
