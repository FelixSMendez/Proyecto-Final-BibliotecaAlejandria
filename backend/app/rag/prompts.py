"""Plantillas controladas para respuestas fundamentadas en fuentes."""

from dataclasses import dataclass

RAG_INSTRUCTIONS = """Eres el bibliotecario virtual de La Biblioteca de Alejandría.
Responde en español y utiliza únicamente el contexto proporcionado.
Incluye referencias como [Fuente 1] junto a cada afirmación relevante.
Si el contexto no es suficiente, indícalo claramente y no inventes información.
Mantén una respuesta clara, útil y concisa."""


@dataclass(frozen=True)
class PromptChunk:
    """Fragmento numerado incluido en el contexto del modelo."""

    title: str
    content: str


def build_rag_input(
    *, question: str, chunks: list[PromptChunk], history: list[tuple[str, str]]
) -> str:
    """Compone memoria breve, contexto recuperado y pregunta actual."""
    history_text = "\n".join(f"{role}: {content}" for role, content in history)
    context_text = "\n\n".join(
        f"[Fuente {index}] {chunk.title}\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    )
    sections = []
    if history_text:
        sections.append(f"Historial reciente:\n{history_text}")
    sections.append(f"Contexto recuperado:\n{context_text}")
    sections.append(f"Pregunta del usuario:\n{question}")
    return "\n\n".join(sections)
