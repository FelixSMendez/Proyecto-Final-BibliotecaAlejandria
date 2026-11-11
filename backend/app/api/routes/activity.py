"""Endpoints de servicios de IA, historial, cuotas y reportes."""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.models import AiService, Book, Conversation, Message, ServiceExecution, User
from app.schemas.activity import (
    AiServiceRead,
    AiServiceUpdate,
    ConversationDetail,
    ConversationReportRow,
    ConversationSummary,
    MessageRead,
    ReportSummary,
    UsageReportRow,
    UsageSummary,
)
from app.services.usage import build_usage_summary, ensure_current_token_period

router = APIRouter(tags=["Actividad y consumo"])


@router.get("/ai-services", response_model=list[AiServiceRead])
def list_ai_services(db: DbSession, _: CurrentUser) -> list[AiService]:
    """Lista los servicios de IA disponibles y su configuración pública."""
    return list(db.scalars(select(AiService).order_by(AiService.id)).all())


@router.patch("/ai-services/{service_id}", response_model=AiServiceRead)
def update_ai_service(
    service_id: int,
    payload: AiServiceUpdate,
    db: DbSession,
    _: AdminUser,
) -> AiService:
    """Permite al administrador activar y limitar un servicio de IA."""
    service = db.get(AiService, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Servicio de IA no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service


def conversation_summary(conversation: Conversation) -> ConversationSummary:
    """Resume una conversación sin cargar su contenido en la respuesta."""
    return ConversationSummary(
        id=conversation.id,
        service_code=conversation.service.code,
        service_name=conversation.service.name,
        title=conversation.title,
        status=conversation.status,
        message_count=len(conversation.messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/history", response_model=list[ConversationSummary])
def list_history(
    db: DbSession,
    current_user: CurrentUser,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ConversationSummary]:
    """Devuelve el historial paginado del usuario autenticado."""
    statement = (
        select(Conversation)
        .options(selectinload(Conversation.service), selectinload(Conversation.messages))
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [conversation_summary(item) for item in db.scalars(statement).all()]


@router.get("/history/{conversation_id}", response_model=ConversationDetail)
def read_history(
    conversation_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ConversationDetail:
    """Devuelve mensajes y fuentes respetando propiedad o rol administrador."""
    statement = (
        select(Conversation)
        .options(selectinload(Conversation.service), selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conversation = db.scalar(statement)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if conversation.user_id != current_user.id and current_user.role.code != "admin":
        raise HTTPException(status_code=403, detail="No puede consultar esta conversación")

    summary = conversation_summary(conversation)
    return ConversationDetail(
        **summary.model_dump(),
        messages=[MessageRead.model_validate(item) for item in conversation.messages],
    )


@router.get("/usage/me", response_model=UsageSummary)
def read_my_usage(db: DbSession, current_user: CurrentUser) -> UsageSummary:
    """Informa la cuota vigente y persiste un reinicio mensual pendiente."""
    changed = ensure_current_token_period(current_user)
    if changed:
        db.commit()
    return build_usage_summary(current_user)


@router.get("/reports/usage", response_model=list[UsageReportRow])
def report_usage(
    db: DbSession,
    _: AdminUser,
    user_id: uuid.UUID | None = None,
    service_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[UsageReportRow]:
    """Agrega consumo diario con filtros compatibles con Power BI."""
    execution_date = cast(ServiceExecution.created_at, Date).label("execution_date")
    statement = (
        select(
            User.id.label("user_id"),
            User.email.label("email"),
            AiService.code.label("service_code"),
            AiService.name.label("service_name"),
            ServiceExecution.model_name,
            execution_date,
            func.count(ServiceExecution.id).label("request_count"),
            func.sum(ServiceExecution.prompt_tokens).label("prompt_tokens"),
            func.sum(ServiceExecution.completion_tokens).label("completion_tokens"),
            func.sum(ServiceExecution.total_tokens).label("total_tokens"),
            func.sum(case((ServiceExecution.status == "success", 1), else_=0)).label(
                "success_count"
            ),
            func.sum(case((ServiceExecution.status == "failed", 1), else_=0)).label(
                "failed_count"
            ),
            func.avg(ServiceExecution.duration_ms).label("average_duration_ms"),
        )
        .join(User, User.id == ServiceExecution.user_id)
        .join(AiService, AiService.id == ServiceExecution.service_id)
        .group_by(
            User.id,
            User.email,
            AiService.code,
            AiService.name,
            ServiceExecution.model_name,
            execution_date,
        )
        .order_by(execution_date.desc(), User.email, AiService.code)
    )
    if user_id is not None:
        statement = statement.where(ServiceExecution.user_id == user_id)
    if service_code:
        statement = statement.where(AiService.code == service_code)
    if date_from:
        statement = statement.where(cast(ServiceExecution.created_at, Date) >= date_from)
    if date_to:
        statement = statement.where(cast(ServiceExecution.created_at, Date) <= date_to)

    return [UsageReportRow.model_validate(row._mapping) for row in db.execute(statement).all()]


@router.get("/reports/conversations", response_model=list[ConversationReportRow])
def report_conversations(
    db: DbSession,
    _: AdminUser,
    user_id: uuid.UUID | None = None,
    service_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ConversationReportRow]:
    """Expone conversaciones agregadas sin duplicar filas por mensajes."""
    message_stats = (
        select(Message.conversation_id, func.count(Message.id).label("message_count"))
        .group_by(Message.conversation_id)
        .subquery()
    )
    execution_stats = (
        select(
            ServiceExecution.conversation_id,
            func.count(ServiceExecution.id).label("request_count"),
            func.coalesce(func.sum(ServiceExecution.total_tokens), 0).label("total_tokens"),
            func.avg(ServiceExecution.duration_ms).label("average_duration_ms"),
        )
        .where(ServiceExecution.conversation_id.is_not(None))
        .group_by(ServiceExecution.conversation_id)
        .subquery()
    )
    statement = (
        select(
            Conversation.id.label("conversation_id"),
            User.id.label("user_id"),
            User.email.label("email"),
            AiService.code.label("service_code"),
            AiService.name.label("service_name"),
            Conversation.title,
            Conversation.status,
            func.coalesce(message_stats.c.message_count, 0).label("message_count"),
            func.coalesce(execution_stats.c.request_count, 0).label("request_count"),
            func.coalesce(execution_stats.c.total_tokens, 0).label("total_tokens"),
            execution_stats.c.average_duration_ms,
            Conversation.created_at,
            Conversation.updated_at,
        )
        .join(User, User.id == Conversation.user_id)
        .join(AiService, AiService.id == Conversation.service_id)
        .outerjoin(message_stats, message_stats.c.conversation_id == Conversation.id)
        .outerjoin(execution_stats, execution_stats.c.conversation_id == Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    if user_id is not None:
        statement = statement.where(Conversation.user_id == user_id)
    if service_code:
        statement = statement.where(AiService.code == service_code)
    if date_from:
        statement = statement.where(cast(Conversation.created_at, Date) >= date_from)
    if date_to:
        statement = statement.where(cast(Conversation.created_at, Date) <= date_to)
    return [
        ConversationReportRow.model_validate(row._mapping)
        for row in db.execute(statement).all()
    ]


@router.get("/reports/summary", response_model=ReportSummary)
def report_summary(db: DbSession, _: AdminUser) -> ReportSummary:
    """Resume actividad global para el panel y Power BI."""
    execution = db.execute(
        select(
            func.count(ServiceExecution.id),
            func.coalesce(func.sum(ServiceExecution.total_tokens), 0),
            func.sum(case((ServiceExecution.status == "success", 1), else_=0)),
            func.sum(case((ServiceExecution.status == "failed", 1), else_=0)),
            func.avg(ServiceExecution.duration_ms),
        )
    ).one()
    return ReportSummary(
        active_users=db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
        active_books=db.scalar(select(func.count(Book.id)).where(Book.is_active.is_(True))) or 0,
        conversations=db.scalar(select(func.count(Conversation.id))) or 0,
        requests=execution[0] or 0,
        total_tokens=execution[1] or 0,
        successful_requests=execution[2] or 0,
        failed_requests=execution[3] or 0,
        average_duration_ms=float(execution[4]) if execution[4] is not None else None,
    )
