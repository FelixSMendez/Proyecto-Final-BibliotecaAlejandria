# La Biblioteca de Alejandría

Aplicación web de consulta, recomendación e investigación de libros asistida por inteligencia artificial.

## Estado actual

- Esquema PostgreSQL y datos de demostración.
- Backend FastAPI con autenticación, catálogo y tres servicios de IA.
- RAG, recomendación e investigación con fuentes auditables.
- Reportes administrativos preparados para el frontend y Power BI.
- Pruebas automatizadas e integración continua del backend.
- Estructura reservada para frontend, Power BI y documentación.

Las decisiones funcionales y técnicas se conservan en `PROJECT_CONTEXT.md`.

## Inicio local con Docker

```bash
docker compose up --build
```

Servicios:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5433` (el puerto `5432` se usa dentro de Docker)

Usuarios locales y detalles del esquema se encuentran en `database/README.md`.

## Desarrollo del backend

```bash
cd backend
uv sync
uv run ruff check .
uv run pytest
uv run uvicorn app.main:app --reload
```
