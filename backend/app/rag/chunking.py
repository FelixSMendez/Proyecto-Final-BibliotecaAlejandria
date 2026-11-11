"""Preparación determinista de documentos para indexación vectorial."""

import re

from app.models import Book


def normalize_text(text: str) -> str:
    """Reduce espacios repetidos sin eliminar separaciones de párrafo."""
    paragraphs = [re.sub(r"\s+", " ", item).strip() for item in text.splitlines()]
    return "\n\n".join(item for item in paragraphs if item)


def estimate_tokens(text: str) -> int:
    """Estima tokens para control preventivo sin depender del tokenizador."""
    return max(1, len(text) // 4)


def split_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Divide por palabras y conserva un solapamiento estable entre fragmentos."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    if overlap >= chunk_size:
        raise ValueError("El solapamiento debe ser menor que el tamaño del fragmento")

    words = normalized.split(" ")
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and current_length + extra > chunk_size:
            chunks.append(" ".join(current))
            overlap_words: list[str] = []
            overlap_length = 0
            for previous in reversed(current):
                if overlap_length + len(previous) + 1 > overlap:
                    break
                overlap_words.append(previous)
                overlap_length += len(previous) + 1
            current = list(reversed(overlap_words))
            current_length = len(" ".join(current))

        current.append(word)
        current_length += len(word) + (1 if len(current) > 1 else 0)

    if current:
        chunks.append(" ".join(current))
    return chunks


def build_book_document(book: Book) -> str:
    """Convierte metadatos y relaciones de un libro en una fuente legible."""
    authors = ", ".join(
        link.author.full_name
        for link in sorted(book.author_links, key=lambda item: item.author_order)
    )
    genres = ", ".join(sorted(link.genre.name for link in book.genre_links))
    fields = [
        f"Título: {book.title}",
        f"Subtítulo: {book.subtitle}" if book.subtitle else None,
        f"Autores: {authors}" if authors else None,
        f"Géneros: {genres}" if genres else None,
        f"Editorial: {book.publisher.name}" if book.publisher else None,
        f"Año de publicación: {book.publication_year}" if book.publication_year else None,
        f"Idioma: {book.language_code}",
        f"Número de páginas: {book.page_count}" if book.page_count else None,
        f"ISBN-10: {book.isbn_10}" if book.isbn_10 else None,
        f"ISBN-13: {book.isbn_13}" if book.isbn_13 else None,
        f"Sinopsis: {book.synopsis}" if book.synopsis else None,
    ]
    return normalize_text("\n".join(field for field in fields if field))
