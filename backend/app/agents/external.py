"""Clientes controlados para consultar fuentes bibliográficas externas."""

from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import Settings


class ExternalResearchError(RuntimeError):
    """Indica que ninguna fuente externa respondió correctamente."""


@dataclass(frozen=True)
class ExternalSourceData:
    """Fuente externa normalizada para generación y auditoría."""

    provider: str
    external_id: str | None
    title: str
    url: str
    excerpt: str
    metadata: dict = field(default_factory=dict)


class ExternalResearchClient(Protocol):
    """Contrato de búsqueda para agentes de investigación."""

    def search(self, query: str, limit: int) -> list[ExternalSourceData]:
        """Busca y normaliza un conjunto acotado de fuentes."""

    def close(self) -> None:
        """Libera los recursos de transporte del cliente."""


class HttpExternalResearchClient:
    """Consulta Open Library y Wikipedia mediante sus APIs públicas."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        """Configura tiempos límite y una identificación explícita del cliente."""
        self.client = httpx.Client(
            timeout=settings.external_api_timeout_seconds,
            headers={"User-Agent": settings.external_api_user_agent},
            transport=transport,
        )
        self.wikimedia_user_agent = settings.wikimedia_user_agent

    def close(self) -> None:
        """Cierra conexiones HTTP reutilizables al finalizar la solicitud."""
        self.client.close()

    def search(self, query: str, limit: int) -> list[ExternalSourceData]:
        """Combina resultados de ambos proveedores y tolera fallos parciales."""
        per_provider = max(1, (limit + 1) // 2)
        sources: list[ExternalSourceData] = []
        failures = 0
        operations = [self._search_open_library]
        if self.wikimedia_user_agent:
            operations.append(self._search_wikipedia)
        for operation in operations:
            try:
                sources.extend(operation(query, per_provider))
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                failures += 1
        if failures == len(operations):
            raise ExternalResearchError("Las fuentes externas no están disponibles")
        return sources[:limit]

    def _search_open_library(self, query: str, limit: int) -> list[ExternalSourceData]:
        """Busca obras y conserva solo campos estables del API de Open Library."""
        response = self.client.get(
            "https://openlibrary.org/search.json",
            params={
                "q": query,
                "limit": limit,
                "fields": "key,title,author_name,first_publish_year,subject",
                "lang": "es",
            },
        )
        response.raise_for_status()
        results = []
        for item in response.json().get("docs", []):
            key = str(item.get("key", ""))
            if key and not key.startswith("/"):
                key = f"/works/{key}"
            title = str(item.get("title", "")).strip()
            if not key or not title:
                continue
            authors = ", ".join(item.get("author_name", [])[:3])
            year = item.get("first_publish_year")
            subjects = ", ".join(item.get("subject", [])[:5])
            details = (
                f"Autores: {authors}" if authors else "",
                f"Año: {year}" if year else "",
                f"Temas: {subjects}" if subjects else "",
            )
            excerpt = "; ".join(part for part in details if part)
            results.append(
                ExternalSourceData(
                    provider="open_library",
                    external_id=key.rsplit("/", maxsplit=1)[-1],
                    title=title,
                    url=f"https://openlibrary.org{key}",
                    excerpt=excerpt,
                    metadata={"authors": item.get("author_name", []), "year": year},
                )
            )
        return results

    def _search_wikipedia(self, query: str, limit: int) -> list[ExternalSourceData]:
        """Recupera extractos introductorios en español mediante MediaWiki."""
        response = self.client.get(
            "https://es.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": limit,
                "prop": "extracts|info",
                "exintro": 1,
                "explaintext": 1,
                "exchars": 1200,
                "inprop": "url",
                "redirects": 1,
                "format": "json",
                "formatversion": 2,
            },
            headers={
                "User-Agent": self.wikimedia_user_agent,
                "Api-User-Agent": self.wikimedia_user_agent,
            },
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", [])
        return [
            ExternalSourceData(
                provider="wikipedia",
                external_id=str(page.get("pageid")) if page.get("pageid") else None,
                title=str(page.get("title", "Sin título")),
                url=str(page.get("canonicalurl") or page.get("fullurl") or ""),
                excerpt=str(page.get("extract", ""))[:1200],
                metadata={"page_id": page.get("pageid")},
            )
            for page in pages
            if page.get("canonicalurl") or page.get("fullurl")
        ]
