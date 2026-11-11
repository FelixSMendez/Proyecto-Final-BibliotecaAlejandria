"""Amplía el catálogo demostrativo con obras canónicas.

Revision ID: 0005_extended_catalog_seed
Revises: 0004_execution_model
Create Date: 2026-11-10
"""

from collections.abc import Sequence
from urllib.parse import quote_plus
from uuid import UUID, uuid5

import sqlalchemy as sa
from alembic import op

from app.data.catalog_seed_v1 import AUTHORS, BOOKS, GENRES

revision: str = "0005_extended_catalog_seed"
down_revision: str | None = "0004_execution_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "alejandria_seed_v1"
SEED_NAMESPACE = UUID("9a60cb0e-6ba9-4ee5-a696-34aa9f157fb9")


def _stable_id(entity: str, slug: str) -> str:
    """Genera UUID estables para que la carga pueda repetirse sin duplicar datos."""
    return str(uuid5(SEED_NAMESPACE, f"{entity}:{slug}"))


def _ensure_genres(connection: sa.Connection) -> dict[str, int]:
    """Crea únicamente los géneros faltantes y devuelve sus identificadores."""
    result: dict[str, int] = {}
    next_id = connection.execute(
        sa.text("SELECT COALESCE(MAX(id), 0) + 1 FROM genres")
    ).scalar_one()
    for name, description in GENRES.items():
        genre_id = connection.execute(
            sa.text("SELECT id FROM genres WHERE lower(name) = lower(:name)"), {"name": name}
        ).scalar_one_or_none()
        if genre_id is None:
            genre_id = next_id
            next_id += 1
            connection.execute(
                sa.text(
                    "INSERT INTO genres (id, name, description) "
                    "VALUES (:id, :name, :description)"
                ),
                {"id": genre_id, "name": name, "description": description},
            )
        result[name] = genre_id
    connection.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('genres', 'id'), "
            "GREATEST((SELECT MAX(id) FROM genres), 1), TRUE)"
        )
    )
    return result


def _ensure_authors(connection: sa.Connection) -> dict[str, str]:
    """Reutiliza autores existentes por identidad externa o nombre exacto."""
    result: dict[str, str] = {}
    for slug, (name, country_code) in AUTHORS.items():
        author_id = connection.execute(
            sa.text(
                "SELECT id FROM authors "
                "WHERE external_source = :source AND external_id = :external_id"
            ),
            {"source": SOURCE, "external_id": slug},
        ).scalar_one_or_none()
        if author_id is None:
            author_id = connection.execute(
                sa.text("SELECT id FROM authors WHERE lower(full_name) = lower(:name) LIMIT 1"),
                {"name": name},
            ).scalar_one_or_none()
        if author_id is None:
            author_id = _stable_id("author", slug)
            connection.execute(
                sa.text(
                    "INSERT INTO authors "
                    "(id, full_name, country_code, external_source, external_id) "
                    "VALUES (:id, :name, :country_code, :source, :external_id)"
                ),
                {
                    "id": author_id,
                    "name": name,
                    "country_code": country_code,
                    "source": SOURCE,
                    "external_id": slug,
                },
            )
        else:
            connection.execute(
                sa.text(
                    "UPDATE authors SET "
                    "country_code = COALESCE(country_code, :country_code), "
                    "external_source = COALESCE(external_source, :source), "
                    "external_id = COALESCE(external_id, :external_id) "
                    "WHERE id = :id"
                ),
                {
                    "id": author_id,
                    "country_code": country_code,
                    "source": SOURCE,
                    "external_id": slug,
                },
            )
        result[slug] = str(author_id)
    return result


def _ensure_book(
    connection: sa.Connection,
    *,
    slug: str,
    title: str,
    author_name: str,
    year: int | None,
    synopsis: str,
) -> str:
    """Inserta una obra o completa un registro previo con el mismo título."""
    book_id = connection.execute(
        sa.text(
            "SELECT id FROM books "
            "WHERE external_source = :source AND external_id = :external_id"
        ),
        {"source": SOURCE, "external_id": slug},
    ).scalar_one_or_none()
    if book_id is None:
        book_id = connection.execute(
            sa.text("SELECT id FROM books WHERE lower(title) = lower(:title) LIMIT 1"),
            {"title": title},
        ).scalar_one_or_none()

    source_url = f"https://openlibrary.org/search?q={quote_plus(f'{title} {author_name}')}"
    values = {
        "id": book_id or _stable_id("book", slug),
        "title": title,
        "synopsis": synopsis,
        "year": year,
        "source_url": source_url,
        "source": SOURCE,
        "external_id": slug,
    }
    if book_id is None:
        connection.execute(
            sa.text(
                "INSERT INTO books "
                "(id, title, synopsis, publication_year, language_code, source_url, "
                "external_source, external_id, is_active) "
                "VALUES (:id, :title, :synopsis, :year, 'es', :source_url, "
                ":source, :external_id, TRUE)"
            ),
            values,
        )
    else:
        connection.execute(
            sa.text(
                "UPDATE books SET "
                "synopsis = COALESCE(synopsis, :synopsis), "
                "publication_year = COALESCE(publication_year, :year), "
                "source_url = COALESCE(source_url, :source_url), "
                "external_source = COALESCE(external_source, :source), "
                "external_id = COALESCE(external_id, :external_id) "
                "WHERE id = :id"
            ),
            values,
        )
    return str(values["id"])


def upgrade() -> None:
    """Carga el catálogo ampliado conservando los datos manuales existentes."""
    connection = op.get_bind()
    genre_ids = _ensure_genres(connection)
    author_ids = _ensure_authors(connection)

    for slug, title, author_slug, year, genres, synopsis in BOOKS:
        author_name = AUTHORS[author_slug][0]
        book_id = _ensure_book(
            connection,
            slug=slug,
            title=title,
            author_name=author_name,
            year=year,
            synopsis=synopsis,
        )
        connection.execute(
            sa.text(
                "INSERT INTO book_authors (book_id, author_id, author_order, contribution) "
                "VALUES (:book_id, :author_id, 1, 'author') ON CONFLICT DO NOTHING"
            ),
            {"book_id": book_id, "author_id": author_ids[author_slug]},
        )
        for genre in genres:
            connection.execute(
                sa.text(
                    "INSERT INTO book_genres (book_id, genre_id) "
                    "VALUES (:book_id, :genre_id) ON CONFLICT DO NOTHING"
                ),
                {"book_id": book_id, "genre_id": genre_ids[genre]},
            )


def downgrade() -> None:
    """Retira solo los registros creados por esta versión del catálogo."""
    connection = op.get_bind()
    for slug, *_ in reversed(BOOKS):
        stable_id = _stable_id("book", slug)
        connection.execute(
            sa.text("DELETE FROM books WHERE id = :id AND external_source = :source"),
            {"id": stable_id, "source": SOURCE},
        )
        connection.execute(
            sa.text(
                "UPDATE books SET external_source = NULL, external_id = NULL "
                "WHERE external_source = :source AND external_id = :external_id"
            ),
            {"source": SOURCE, "external_id": slug},
        )

    for slug in AUTHORS:
        stable_id = _stable_id("author", slug)
        connection.execute(
            sa.text(
                "DELETE FROM authors WHERE id = :id AND external_source = :source "
                "AND NOT EXISTS (SELECT 1 FROM book_authors WHERE author_id = :id)"
            ),
            {"id": stable_id, "source": SOURCE},
        )
        connection.execute(
            sa.text(
                "UPDATE authors SET external_source = NULL, external_id = NULL "
                "WHERE external_source = :source AND external_id = :external_id"
            ),
            {"source": SOURCE, "external_id": slug},
        )

    for name in GENRES:
        connection.execute(
            sa.text(
                "DELETE FROM genres WHERE name = :name "
                "AND NOT EXISTS (SELECT 1 FROM book_genres WHERE genre_id = genres.id)"
            ),
            {"name": name},
        )
