"""Pruebas unitarias de preparación y configuración del RAG."""

from types import SimpleNamespace

import pytest
from google.genai import errors

from app.core.config import Settings
from app.rag.chunking import build_book_document, estimate_tokens, split_text
from app.rag.prompts import PromptChunk, build_rag_input
from app.rag.providers import (
    AiProviderConfigurationError,
    AiProviderUnavailableError,
    GeminiProvider,
    get_ai_provider,
)


def test_split_text_preserves_content_and_overlap() -> None:
    """Verifica que la fragmentación sea estable y no produzca vacíos."""
    text = " ".join(f"palabra{i}" for i in range(80))

    chunks = split_text(text, chunk_size=120, overlap=25)

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 130 for chunk in chunks)


def test_estimate_tokens_is_positive() -> None:
    """Mantiene una reserva mínima incluso para textos breves."""
    assert estimate_tokens("hola") == 1
    assert estimate_tokens("a" * 400) == 100


def test_build_book_document_includes_relationships() -> None:
    """Incluye autores y géneros cargados en el documento fuente."""
    author = SimpleNamespace(full_name="Mary Shelley")
    genre = SimpleNamespace(name="Terror gótico")
    book = SimpleNamespace(
        title="Frankenstein",
        subtitle=None,
        author_links=[SimpleNamespace(author=author, author_order=1)],
        genre_links=[SimpleNamespace(genre=genre)],
        publisher=None,
        publication_year=1818,
        language_code="es",
        page_count=280,
        isbn_10=None,
        isbn_13=None,
        synopsis="Una reflexión sobre creación y responsabilidad.",
    )

    document = build_book_document(book)

    assert "Mary Shelley" in document
    assert "Terror gótico" in document
    assert "1818" in document


def test_prompt_numbers_sources_and_includes_history() -> None:
    """Conserva memoria breve y referencias numeradas."""
    prompt = build_rag_input(
        question="¿De qué trata?",
        chunks=[PromptChunk(title="Frankenstein", content="Contenido relevante")],
        history=[("user", "Busco una novela gótica")],
    )

    assert "[Fuente 1]" in prompt
    assert "Busco una novela gótica" in prompt
    assert "¿De qué trata?" in prompt


def test_provider_requires_configuration() -> None:
    """Evita construir el cliente OpenAI sin credenciales."""
    settings = Settings(
        ai_provider="openai",
        ai_api_key=None,
        ai_chat_model="modelo-chat",
        ai_embedding_model="text-embedding-3-small",
    )

    with pytest.raises(AiProviderConfigurationError, match="AI_API_KEY"):
        get_ai_provider(settings)


def test_gemini_provider_requires_configuration() -> None:
    """Evita construir el cliente Gemini sin su clave privada."""
    settings = Settings(
        ai_provider="gemini",
        gemini_api_key=None,
        ai_chat_model="gemini-3.8-flash",
        ai_embedding_model="gemini-embedding-001",
    )

    with pytest.raises(AiProviderConfigurationError, match="GEMINI_API_KEY"):
        get_ai_provider(settings)


def test_gemini_provider_uses_retrieval_tasks_and_reports_usage(monkeypatch) -> None:
    """Comprueba el contrato Gemini sin realizar solicitudes externas."""
    calls: dict[str, object] = {}

    class FakeModels:
        """Simula las operaciones del SDK que utiliza el adaptador."""

        def embed_content(self, **kwargs):
            calls["embedding"] = kwargs
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.5] * 1536)],
            )

        def generate_content(self, **kwargs):
            calls["generation"] = kwargs
            return SimpleNamespace(
                text="Respuesta basada en el catálogo",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=12,
                    candidates_token_count=7,
                ),
            )

    monkeypatch.setattr(
        "app.rag.providers.genai.Client",
        lambda **_: SimpleNamespace(models=FakeModels()),
    )
    provider = get_ai_provider(
        Settings(
            ai_provider="gemini",
            gemini_api_key="clave-de-prueba",
            ai_chat_model="gemini-3.8-flash",
            ai_embedding_model="gemini-embedding-001",
        )
    )

    assert isinstance(provider, GeminiProvider)
    embedding = provider.embed(["consulta"], task_type="query")
    generation = provider.generate(
        instructions="Responde con fuentes.",
        input_text="Contexto de prueba",
        max_output_tokens=200,
        safety_identifier="usuario-anonimo",
    )

    embedding_config = calls["embedding"]["config"]
    assert embedding_config.task_type == "RETRIEVAL_QUERY"
    assert embedding_config.output_dimensionality == 1536
    generation_config = calls["generation"]["config"]
    assert generation_config.thinking_config.thinking_budget == 0
    assert len(embedding.vectors[0]) == 1536
    assert generation.text == "Respuesta basada en el catálogo"
    assert generation.input_tokens == 12
    assert generation.output_tokens == 7


def test_gemini_provider_retries_transient_errors(monkeypatch) -> None:
    """Reintenta saturación temporal y devuelve un error estable al agotarse."""
    attempts = 0

    class UnavailableModels:
        """Simula una saturación persistente del modelo."""

        def generate_content(self, **kwargs):
            nonlocal attempts
            attempts += 1
            raise errors.APIError(
                503,
                {"error": {"code": 503, "status": "UNAVAILABLE", "message": "High demand"}},
            )

    monkeypatch.setattr(
        "app.rag.providers.genai.Client",
        lambda **_: SimpleNamespace(models=UnavailableModels()),
    )
    monkeypatch.setattr("app.rag.providers.time.sleep", lambda _: None)
    provider = get_ai_provider(
        Settings(
            ai_provider="gemini",
            gemini_api_key="clave-de-prueba",
            ai_chat_model="gemini-3.8-flash",
            ai_embedding_model="gemini-embedding-001",
            ai_retry_attempts=3,
        )
    )

    with pytest.raises(AiProviderUnavailableError, match="temporalmente"):
        provider.generate(
            instructions="Responde con fuentes.",
            input_text="Contexto de prueba",
            max_output_tokens=200,
            safety_identifier="usuario-anonimo",
        )

    assert attempts == 3
