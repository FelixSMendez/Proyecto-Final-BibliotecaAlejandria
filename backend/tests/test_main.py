"""Pruebas de disponibilidad y contrato OpenAPI."""

from app.main import app, health_check


def test_health_check() -> None:
    response = health_check()

    assert response["status"] == "ok"


def test_openapi_contains_main_routes() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/auth/login" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/catalog/books" in paths
    assert "/api/v1/history" in paths
    assert "/api/v1/usage/me" in paths
    assert "/api/v1/reports/usage" in paths
    assert "/api/v1/ai/chat" in paths
    assert "/api/v1/ai/recommend" in paths
    assert "/api/v1/ai/research" in paths
    assert "/api/v1/rag/books/{book_id}/index" in paths
    assert "/api/v1/rag/books/index-all" in paths
    assert "/api/v1/rag/books/status" in paths
    assert "/api/v1/rag/documents" in paths
    assert "/api/v1/reports/conversations" in paths
    assert "/api/v1/reports/summary" in paths
