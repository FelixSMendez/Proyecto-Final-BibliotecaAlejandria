# Agentes literarios

## Recomendador

`POST /api/v1/ai/recommend` recibe preferencias textuales y filtros opcionales. El backend descarta
libros incompatibles, puntúa coincidencias y entrega a Gemini un conjunto máximo de diez candidatos.
La respuesta solo puede recomendar obras del catálogo.

```json
{
  "query": "Quiero una novela gótica breve sobre responsabilidad",
  "genre_ids": [5],
  "language_code": "es",
  "max_pages": 350,
  "limit": 5
}
```

## Investigador

`POST /api/v1/ai/research` recupera contexto vectorial y consulta Open Library y Wikipedia en
español. Tolera que uno de los proveedores externos falle, pero informa un `502` si ambos están
indisponibles. Las fuentes externas se guardan en `external_sources`.

Wikipedia exige un agente identificable con datos de contacto reales. Se habilita configurando:

```text
WIKIMEDIA_USER_AGENT=BibliotecaAlejandriaBot/0.1 (https://proyecto.example; correo@example.com)
```

Si la variable está vacía, la investigación continúa únicamente con Open Library y el catálogo.

```json
{
  "query": "Influencia del romanticismo en Frankenstein",
  "top_k": 4,
  "max_external_sources": 4
}
```

Las búsquedas siguen los contratos públicos de la [Search API de Open Library](https://openlibrary.org/dev/docs/api/search)
y la [Action API de MediaWiki](https://www.mediawiki.org/wiki/API:Search).

## Seguridad y consumo

- Ambos endpoints requieren JWT.
- Los servicios pueden activarse o desactivarse desde `/api/v1/ai-services/{id}`.
- Las cuotas mensuales se validan antes de utilizar el modelo.
- Las respuestas, fuentes, tokens, duración y errores quedan auditados.
- Las claves del proveedor permanecen exclusivamente en el backend.
