"""Registro central de rutas de la versión 1."""

from fastapi import APIRouter

from app.api.routes import activity, agents, auth, catalog, rag, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(catalog.router)
api_router.include_router(activity.router)
api_router.include_router(rag.router)
api_router.include_router(agents.router)
