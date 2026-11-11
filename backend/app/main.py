"""Punto de entrada ASGI y composición de la API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API de catálogo e inteligencia artificial de La Biblioteca de Alejandría.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Sistema"])
def health_check() -> dict[str, str]:
    """Confirma que el proceso HTTP está disponible."""
    return {"status": "ok", "service": settings.app_name}
