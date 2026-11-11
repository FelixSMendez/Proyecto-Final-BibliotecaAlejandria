"""Abstracciones de embeddings y generación para proveedores de IA."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from google import genai
from google.genai import errors, types
from openai import OpenAI

from app.core.config import Settings, get_settings


class AiProviderConfigurationError(RuntimeError):
    """Indica que faltan credenciales o modelos requeridos."""


class AiProviderUnavailableError(RuntimeError):
    """Indica que el proveedor agotó los reintentos por un fallo temporal."""


T = TypeVar("T")


@dataclass(frozen=True)
class EmbeddingBatch:
    """Vectores generados y tokens facturados por el proveedor."""

    vectors: list[list[float]]
    input_tokens: int


@dataclass(frozen=True)
class GeneratedText:
    """Texto generado y consumo reportado por el modelo."""

    text: str
    input_tokens: int
    output_tokens: int


class AiProvider(Protocol):
    """Contrato mínimo que necesita el servicio RAG."""

    def embed(
        self, texts: list[str], *, task_type: Literal["document", "query"] = "document"
    ) -> EmbeddingBatch:
        """Convierte textos no vacíos en vectores ordenados."""

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        safety_identifier: str,
    ) -> GeneratedText:
        """Genera una respuesta textual y reporta su consumo."""


class OpenAiProvider:
    """Implementa el contrato RAG con el SDK oficial de OpenAI."""

    def __init__(self, settings: Settings) -> None:
        """Valida la configuración y crea el cliente oficial."""
        if not settings.ai_api_key:
            raise AiProviderConfigurationError("AI_API_KEY no está configurada")
        if not settings.ai_chat_model:
            raise AiProviderConfigurationError("AI_CHAT_MODEL no está configurado")
        if not settings.ai_embedding_model:
            raise AiProviderConfigurationError("AI_EMBEDDING_MODEL no está configurado")

        self.settings = settings
        self.client = OpenAI(api_key=settings.ai_api_key)

    def embed(
        self, texts: list[str], *, task_type: Literal["document", "query"] = "document"
    ) -> EmbeddingBatch:
        """Solicita embeddings flotantes con dimensión compatible con pgvector."""
        del task_type  # OpenAI no distingue tareas de recuperación en este endpoint.
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Los textos para embeddings no pueden estar vacíos")

        response = self.client.embeddings.create(
            model=self.settings.ai_embedding_model,
            input=texts,
            encoding_format="float",
            dimensions=self.settings.ai_embedding_dimensions,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return EmbeddingBatch(
            vectors=[item.embedding for item in ordered],
            input_tokens=response.usage.prompt_tokens,
        )

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        safety_identifier: str,
    ) -> GeneratedText:
        """Genera una respuesta sin almacenar estado en el proveedor."""
        response = self.client.responses.create(
            model=self.settings.ai_chat_model,
            instructions=instructions,
            input=input_text,
            max_output_tokens=max_output_tokens,
            safety_identifier=safety_identifier,
            store=False,
        )
        usage = response.usage
        return GeneratedText(
            text=response.output_text.strip(),
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )


class GeminiProvider:
    """Implementa embeddings y generación con Google Gen AI SDK."""

    def __init__(self, settings: Settings) -> None:
        """Valida la configuración y crea el cliente Gemini Developer API."""
        if not settings.gemini_api_key:
            raise AiProviderConfigurationError("GEMINI_API_KEY no está configurada")
        if not settings.ai_chat_model:
            raise AiProviderConfigurationError("AI_CHAT_MODEL no está configurado")
        if not settings.ai_embedding_model:
            raise AiProviderConfigurationError("AI_EMBEDDING_MODEL no está configurado")

        self.settings = settings
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def _call_with_retry(self, operation: Callable[[], T]) -> T:
        """Reintenta errores transitorios con espera exponencial acotada."""
        transient_codes = {429, 500, 502, 503, 504}
        for attempt in range(self.settings.ai_retry_attempts):
            try:
                return operation()
            except errors.APIError as exc:
                is_last_attempt = attempt + 1 == self.settings.ai_retry_attempts
                if exc.code not in transient_codes or is_last_attempt:
                    if exc.code in transient_codes:
                        raise AiProviderUnavailableError(
                            "Gemini no está disponible temporalmente"
                        ) from exc
                    raise
                delay = self.settings.ai_retry_backoff_seconds * (2**attempt)
                time.sleep(delay)
        raise AiProviderUnavailableError("Gemini no está disponible temporalmente")

    def embed(
        self, texts: list[str], *, task_type: Literal["document", "query"] = "document"
    ) -> EmbeddingBatch:
        """Genera vectores Gemini optimizados para documento o consulta."""
        if not texts or any(not text.strip() for text in texts):
            raise ValueError("Los textos para embeddings no pueden estar vacíos")

        gemini_task = "RETRIEVAL_DOCUMENT" if task_type == "document" else "RETRIEVAL_QUERY"
        response = self._call_with_retry(
            lambda: self.client.models.embed_content(
                model=self.settings.ai_embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self.settings.ai_embedding_dimensions,
                    task_type=gemini_task,
                ),
            )
        )
        vectors = [embedding.values or [] for embedding in response.embeddings or []]
        # Gemini informa caracteres facturables; se conserva una estimación comparable en tokens.
        estimated_tokens = sum(max(1, len(text) // 4) for text in texts)
        return EmbeddingBatch(vectors=vectors, input_tokens=estimated_tokens)

    def generate(
        self,
        *,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
        safety_identifier: str,
    ) -> GeneratedText:
        """Genera texto con instrucciones de sistema y reporta tokens Gemini."""
        del safety_identifier  # Gemini Developer API no expone un campo equivalente.
        response = self._call_with_retry(
            lambda: self.client.models.generate_content(
                model=self.settings.ai_chat_model,
                contents=input_text,
                config=types.GenerateContentConfig(
                    system_instruction=instructions,
                    max_output_tokens=max_output_tokens,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=self.settings.ai_thinking_budget,
                        include_thoughts=False,
                    ),
                ),
            )
        )
        usage = response.usage_metadata
        return GeneratedText(
            text=(response.text or "").strip(),
            input_tokens=usage.prompt_token_count if usage and usage.prompt_token_count else 0,
            output_tokens=(
                usage.candidates_token_count if usage and usage.candidates_token_count else 0
            ),
        )


def get_ai_provider(settings: Settings | None = None) -> AiProvider:
    """Construye el proveedor configurado sin filtrar secretos a las rutas."""
    active_settings = settings or get_settings()
    if active_settings.ai_provider == "gemini":
        return GeminiProvider(active_settings)
    if active_settings.ai_provider == "openai":
        return OpenAiProvider(active_settings)
    raise AiProviderConfigurationError(
        f"Proveedor de IA no soportado: {active_settings.ai_provider}"
    )
