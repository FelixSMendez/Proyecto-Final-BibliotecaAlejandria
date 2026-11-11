# Backend FastAPI

## Desarrollo sin Docker

```bash
uv sync
uv run uvicorn app.main:app --reload
```

La API espera que el esquema de `database/` ya esté aplicado en PostgreSQL.

## Migraciones

```bash
uv run alembic upgrade head
uv run alembic current
```

La migración `0005_extended_catalog_seed` incorpora un catálogo reproducible de 120 obras,
56 autores y 15 géneros. Conserva los registros existentes y puede aplicarse a una base ya creada:

```bash
docker compose exec backend alembic upgrade head
```

Después de migrar, un administrador puede generar los embeddings del catálogo desde
`POST /api/v1/rag/books/index-all`. Esta operación consume cuota del proveedor de IA.

## Endpoints implementados

- `/api/v1/auth/*`: inicio, renovación y cierre de sesión.
- `/api/v1/users`: administración de usuarios.
- `/api/v1/catalog/*`: libros, autores, géneros y editoriales.
- `/api/v1/ai-services`: configuración de servicios de IA.
- `/api/v1/history`: historial propio de conversaciones.
- `/api/v1/usage/me`: consumo y límite mensual del usuario.
- `/api/v1/reports/usage`: reporte administrativo para web y Power BI.
- `/api/v1/rag/books/{book_id}/index`: indexación vectorial administrativa.
- `/api/v1/ai/chat`: bibliotecario virtual con RAG, memoria y fuentes.
- `/api/v1/ai/recommend`: recomendaciones explicadas sobre el catálogo activo.
- `/api/v1/ai/research`: investigación con catálogo, Open Library y Wikipedia.
- `/api/v1/rag/books/index-all`: indexación administrativa del catálogo completo.
- `/api/v1/rag/books/status`: estado actual, pendiente o desactualizado del índice.
- `/api/v1/reports/conversations`: conversaciones agregadas para Power BI.
- `/api/v1/reports/summary`: indicadores globales del sistema.

## Configuración de RAG

Copiar `.env.example` como `.env` en la raíz y completar:

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=...
AI_CHAT_MODEL=gemini-3.8-flash
AI_EMBEDDING_MODEL=gemini-embedding-001
AI_EMBEDDING_DIMENSIONS=1536
AI_THINKING_BUDGET=0
RAG_INDEX_BATCH_SIZE=20
```

Los embeddings se generan con 1536 dimensiones para conservar compatibilidad con pgvector.
La indexación agrupa libros para reducir solicitudes al proveedor. El presupuesto de razonamiento
se mantiene en cero para reservar la salida del modelo a las respuestas visibles y sus citas.

## Agentes literarios

El recomendador filtra y puntúa libros activos antes de solicitar una explicación a Gemini. El
investigador combina fragmentos del catálogo con resultados públicos de Open Library y Wikipedia.
Cada respuesta conserva conversación, fuentes, tokens, duración y estado de ejecución.

No se debe guardar `.env` en Git. Después de cambiar las variables, recrear el backend:

```bash
docker compose up -d --force-recreate backend
```

## Calidad

```bash
uv run ruff check .
uv run pytest
```
