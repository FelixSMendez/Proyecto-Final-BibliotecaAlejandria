"""Pruebas de integridad del catálogo curado versionado."""

from app.data.catalog_seed_v1 import AUTHORS, BOOKS, GENRES


def test_extended_catalog_has_expected_coverage() -> None:
    """Protege el tamaño mínimo acordado para la demostración académica."""
    assert len(BOOKS) >= 120
    assert len(AUTHORS) >= 50
    assert len(GENRES) >= 12


def test_extended_catalog_identifiers_are_unique() -> None:
    """Evita que una migración relacione dos obras con la misma identidad."""
    slugs = [book[0] for book in BOOKS]
    titles = [book[1].casefold() for book in BOOKS]

    assert len(slugs) == len(set(slugs))
    assert len(titles) == len(set(titles))


def test_extended_catalog_relations_and_fields_are_valid() -> None:
    """Valida autores, géneros y límites compatibles con los esquemas HTTP."""
    for slug, title, author_slug, year, genres, synopsis in BOOKS:
        assert slug
        assert 0 < len(title) <= 250
        assert author_slug in AUTHORS
        assert year is None or 1000 <= year <= 2100
        assert genres and set(genres).issubset(GENRES)
        assert len(synopsis) >= 40
