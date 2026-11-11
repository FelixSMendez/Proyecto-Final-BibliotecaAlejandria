"""Contratos de servicios de IA, historial y reportes de consumo."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AiServiceRead(BaseModel):
    """Configuración visible de un servicio de IA."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    model_name: str | None
    is_active: bool
    max_tokens_per_request: int


class AiServiceUpdate(BaseModel):
    """Cambios administrativos permitidos sobre un servicio."""

    model_name: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    max_tokens_per_request: int | None = Field(default=None, gt=0, le=100000)


class MessageRead(BaseModel):
    """Mensaje histórico con fuentes y consumo atribuido."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    sources: list[dict]
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime


class ConversationSummary(BaseModel):
    """Resumen ligero para listados de conversaciones."""

    id: uuid.UUID
    service_code: str
    service_name: str
    title: str | None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    """Conversación completa con mensajes ordenados."""

    messages: list[MessageRead]


class UsageSummary(BaseModel):
    """Estado mensual de la cuota de un usuario."""

    user_id: uuid.UUID
    period_start: date
    token_limit: int
    tokens_used: int
    tokens_remaining: int
    usage_percent: float


class UsageReportRow(BaseModel):
    """Fila agregada para reportes web y Power BI."""

    user_id: uuid.UUID
    email: str
    service_code: str
    service_name: str
    model_name: str | None
    execution_date: date
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    success_count: int
    failed_count: int
    average_duration_ms: float | None


class ConversationReportRow(BaseModel):
    """Conversación agregada para auditoría y Power BI."""

    conversation_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    service_code: str
    service_name: str
    title: str | None
    status: str
    message_count: int
    request_count: int
    total_tokens: int
    average_duration_ms: float | None
    created_at: datetime
    updated_at: datetime


class ReportSummary(BaseModel):
    """Indicadores globales para el panel administrativo."""

    active_users: int
    active_books: int
    conversations: int
    requests: int
    total_tokens: int
    successful_requests: int
    failed_requests: int
    average_duration_ms: float | None
