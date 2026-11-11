"""Endpoints de recomendación e investigación literaria."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.external import (
    ExternalResearchClient,
    ExternalResearchError,
    HttpExternalResearchClient,
)
from app.agents.service import recommend_books, research_literature
from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.rag.providers import (
    AiProviderConfigurationError,
    AiProviderUnavailableError,
    get_ai_provider,
)
from app.schemas.agents import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendedBook,
    ResearchRequest,
    ResearchResponse,
    ResearchSource,
)
from app.schemas.rag import RagTokenUsage

router = APIRouter(prefix="/ai", tags=["Agentes literarios"])


def get_external_client() -> Generator[ExternalResearchClient, None, None]:
    """Proporciona un cliente externo aislado por solicitud."""
    client = HttpExternalResearchClient(get_settings())
    try:
        yield client
    finally:
        client.close()


ExternalClient = Annotated[ExternalResearchClient, Depends(get_external_client)]


def configured_provider():
    """Construye el proveedor o traduce una configuración incompleta."""
    try:
        return get_ai_provider()
    except AiProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/recommend",
    response_model=RecommendationResponse,
    responses={
        502: {"description": "El proveedor rechazó la solicitud"},
        503: {"description": "Servicio temporalmente no disponible"},
    },
)
def recommend_readings(
    payload: RecommendationRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> RecommendationResponse:
    """Sugiere libros activos usando filtros, puntuación y explicación."""
    try:
        result = recommend_books(
            db,
            user=current_user,
            request=payload,
            provider=configured_provider(),
        )
    except HTTPException:
        raise
    except AiProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini está temporalmente saturado; intenta nuevamente en unos segundos",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible generar recomendaciones",
        ) from exc
    return RecommendationResponse(
        conversation_id=result.conversation_id,
        answer=result.answer,
        recommendations=[RecommendedBook(**item.__dict__) for item in result.recommendations],
        usage=RagTokenUsage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
        ),
    )


@router.post(
    "/research",
    response_model=ResearchResponse,
    responses={
        502: {"description": "Las fuentes o el proveedor rechazaron la solicitud"},
        503: {"description": "Servicio temporalmente no disponible"},
    },
)
def research_topic(
    payload: ResearchRequest,
    db: DbSession,
    current_user: CurrentUser,
    external_client: ExternalClient,
) -> ResearchResponse:
    """Investiga un tema contrastando catálogo y fuentes públicas."""
    try:
        result = research_literature(
            db,
            user=current_user,
            request=payload,
            provider=configured_provider(),
            external_client=external_client,
        )
    except HTTPException:
        raise
    except AiProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini está temporalmente saturado; intenta nuevamente en unos segundos",
        ) from exc
    except ExternalResearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Las fuentes externas no están disponibles temporalmente",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible completar la investigación",
        ) from exc
    return ResearchResponse(
        conversation_id=result.conversation_id,
        answer=result.answer,
        sources=[ResearchSource(**item.__dict__) for item in result.sources],
        usage=RagTokenUsage(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.prompt_tokens + result.completion_tokens,
        ),
    )
