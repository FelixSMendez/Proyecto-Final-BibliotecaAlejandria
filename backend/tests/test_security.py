"""Pruebas unitarias de contraseñas y tokens."""

import uuid

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("UnaClaveSegura123!")

    assert encoded != "UnaClaveSegura123!"
    assert verify_password("UnaClaveSegura123!", encoded)
    assert not verify_password("incorrecta", encoded)


def test_access_token_round_trip() -> None:
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id, "admin")

    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="Token inválido"):
        decode_access_token("not-a-jwt")


def test_refresh_token_hash_is_deterministic() -> None:
    digest = hash_refresh_token("refresh-token")

    assert digest == hash_refresh_token("refresh-token")
    assert len(digest) == 64
