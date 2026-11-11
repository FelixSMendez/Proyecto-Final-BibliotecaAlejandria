"""Pruebas de periodos, cuotas y acumulación de tokens."""

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models import User
from app.services.usage import (
    assert_token_budget,
    build_usage_summary,
    ensure_current_token_period,
    register_token_usage,
)


def make_user(*, limit: int = 1000, used: int = 200, period: date | None = None) -> User:
    return User(
        id=uuid.uuid4(),
        role_id=2,
        email="test@example.com",
        display_name="Test",
        password_hash="not-used",
        monthly_token_limit=limit,
        monthly_tokens_used=used,
        token_period_start=period or date.today().replace(day=1),
    )


def test_usage_summary_calculates_remaining_tokens() -> None:
    summary = build_usage_summary(make_user())

    assert summary.tokens_remaining == 800
    assert summary.usage_percent == 20.0


def test_token_period_resets_on_new_month() -> None:
    user = make_user(used=900, period=date(2025, 1, 1))

    changed = ensure_current_token_period(user, today=date(2026, 11, 10))

    assert changed
    assert user.monthly_tokens_used == 0
    assert user.token_period_start == date(2026, 11, 1)


def test_token_budget_rejects_request_over_remaining_limit() -> None:
    with pytest.raises(HTTPException) as exc_info:
        assert_token_budget(make_user(limit=1000, used=950), 100)

    assert exc_info.value.status_code == 429


def test_register_token_usage_accumulates_tokens() -> None:
    user = make_user(used=200)

    register_token_usage(user, 125)

    assert user.monthly_tokens_used == 325
