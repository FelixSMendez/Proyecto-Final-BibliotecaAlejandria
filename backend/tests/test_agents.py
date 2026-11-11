"""Pruebas unitarias de agentes y fuentes externas."""

import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.agents.external import ExternalResearchError, HttpExternalResearchClient
from app.agents.service import score_recommendation_candidate
from app.core.config import Settings
from app.schemas.agents import RecommendationRequest


def external_api_handler(request: httpx.Request) -> httpx.Response:
    """Devuelve contratos mínimos de Open Library y MediaWiki."""
    if request.url.host == "openlibrary.org":
        return httpx.Response(
            200,
            json={
                "docs": [
                    {
                        "key": "/works/OL45804W",
                        "title": "Frankenstein",
                        "author_name": ["Mary Shelley"],
                        "first_publish_year": 1818,
                        "subject": ["Gothic fiction"],
                    }
                ]
            },
        )
    return httpx.Response(
        200,
        json={
            "query": {
                "pages": [
                    {
                        "pageid": 123,
                        "title": "Frankenstein o el moderno Prometeo",
                        "canonicalurl": "https://es.wikipedia.org/wiki/Frankenstein",
                        "extract": "Novela de Mary Shelley publicada en 1818.",
                    }
                ]
            }
        },
    )


def test_external_client_normalizes_both_providers() -> None:
    """Combina resultados externos sin filtrar contratos particulares."""
    client = HttpExternalResearchClient(
        Settings(wikimedia_user_agent="BibliotecaAlejandriaBot/0.1 (test@example.com)"),
        transport=httpx.MockTransport(external_api_handler),
    )

    sources = client.search("Frankenstein Mary Shelley", 4)
    client.close()

    assert {source.provider for source in sources} == {"open_library", "wikipedia"}
    assert sources[0].external_id == "OL45804W"
    assert sources[1].url.startswith("https://es.wikipedia.org/")


def test_external_client_reports_total_outage() -> None:
    """Distingue un fallo total de una búsqueda legítimamente vacía."""
    transport = httpx.MockTransport(lambda _: httpx.Response(503))
    client = HttpExternalResearchClient(Settings(), transport=transport)

    with pytest.raises(ExternalResearchError, match="no están disponibles"):
        client.search("realismo mágico", 4)

    client.close()


def test_recommendation_score_applies_filters_and_terms() -> None:
    """Puntúa coincidencias y descarta libros fuera de los filtros."""
    genre = SimpleNamespace(id=5, name="Terror gótico")
    author_id = uuid.uuid4()
    author = SimpleNamespace(id=author_id, full_name="Mary Shelley")
    book = SimpleNamespace(
        title="Frankenstein",
        subtitle=None,
        synopsis="Una novela gótica sobre creación y responsabilidad.",
        language_code="es",
        page_count=280,
        genre_links=[SimpleNamespace(genre_id=5, genre=genre)],
        author_links=[SimpleNamespace(author_id=author_id, author=author)],
    )
    request = RecommendationRequest(
        query="Busco una novela gótica sobre responsabilidad",
        genre_ids=[5],
        language_code="es",
        max_pages=300,
    )

    score = score_recommendation_candidate(book, request)

    assert score is not None and score >= 8
    assert score_recommendation_candidate(
        book,
        request.model_copy(update={"genre_ids": [999]}),
    ) is None


def test_recommendation_keeps_books_with_unknown_page_count() -> None:
    """No excluye obras canónicas cuando la extensión depende de la edición."""
    book = SimpleNamespace(
        title="La máquina del tiempo",
        subtitle=None,
        synopsis="Una novela sobre viajes temporales y transformación social.",
        language_code="es",
        page_count=None,
        genre_links=[],
        author_links=[],
    )
    request = RecommendationRequest(
        query="Busco viajes en el tiempo",
        language_code="es",
        max_pages=350,
    )

    assert score_recommendation_candidate(book, request) is not None
