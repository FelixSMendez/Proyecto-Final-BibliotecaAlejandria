"""Reglas mensuales de cuota y consumo de tokens."""

from datetime import date

from fastapi import HTTPException, status

from app.models import User
from app.schemas.activity import UsageSummary


def current_period_start(today: date | None = None) -> date:
    """Calcula el primer día del periodo mensual vigente."""
    value = today or date.today()
    return value.replace(day=1)


def ensure_current_token_period(user: User, today: date | None = None) -> bool:
    """Reinicia el contador cuando el usuario entra en un mes nuevo."""
    period_start = current_period_start(today)
    if user.token_period_start != period_start:
        user.token_period_start = period_start
        user.monthly_tokens_used = 0
        return True
    return False


def assert_token_budget(user: User, requested_tokens: int) -> None:
    """Bloquea solicitudes que exceden el saldo mensual disponible."""
    ensure_current_token_period(user)
    remaining = max(user.monthly_token_limit - user.monthly_tokens_used, 0)
    if requested_tokens <= 0:
        raise ValueError("requested_tokens debe ser positivo")
    if remaining < requested_tokens:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Límite mensual de tokens insuficiente",
                "tokens_remaining": remaining,
                "tokens_requested": requested_tokens,
            },
        )


def register_token_usage(user: User, total_tokens: int) -> None:
    """Acumula tokens confirmados después de ejecutar un servicio."""
    if total_tokens < 0:
        raise ValueError("total_tokens no puede ser negativo")
    ensure_current_token_period(user)
    user.monthly_tokens_used += total_tokens


def build_usage_summary(user: User) -> UsageSummary:
    """Construye el resumen de cuota presentado por la API."""
    ensure_current_token_period(user)
    remaining = max(user.monthly_token_limit - user.monthly_tokens_used, 0)
    percent = (
        round((user.monthly_tokens_used / user.monthly_token_limit) * 100, 2)
        if user.monthly_token_limit
        else 100.0
    )
    return UsageSummary(
        user_id=user.id,
        period_start=user.token_period_start,
        token_limit=user.monthly_token_limit,
        tokens_used=user.monthly_tokens_used,
        tokens_remaining=remaining,
        usage_percent=percent,
    )
