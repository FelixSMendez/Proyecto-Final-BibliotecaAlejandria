"""Pruebas de validación para contratos de entrada."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.catalog import AuthorCreate, BookCreate
from app.schemas.users import UserCreate


def test_user_requires_valid_email_and_password() -> None:
    with pytest.raises(ValidationError):
        UserCreate(email="incorrecto", display_name="Lector", password="corta")


def test_book_requires_at_least_one_author() -> None:
    with pytest.raises(ValidationError):
        BookCreate(title="Libro", author_ids=[])


def test_valid_book_schema() -> None:
    payload = BookCreate(
        title="El libro de prueba",
        author_ids=[uuid.uuid4()],
        genre_ids=[1, 2],
        publication_year=2026,
    )

    assert payload.language_code == "es"


def test_author_rejects_invalid_life_dates() -> None:
    with pytest.raises(ValidationError):
        AuthorCreate(
            full_name="Autor",
            birth_date="2000-01-01",
            death_date="1990-01-01",
        )
