# Frontend de La Biblioteca de Alejandría

Aplicación React + TypeScript construida sobre el backend FastAPI del proyecto.

```powershell
pnpm install
pnpm dev
```

También puede iniciarse junto al backend y PostgreSQL desde la raíz:

```powershell
docker compose up --build
```

La URL de la API se configura en `.env` mediante `VITE_API_URL`.

## Módulos

- Autenticación con renovación de sesión.
- Catálogo y búsqueda.
- Bibliotecario RAG, recomendador e investigador.
- Historial y consumo mensual.
- Panel administrativo con usuarios, índice RAG y reportes.

Los conceptos visuales aprobados se conservan en `public/design/`.

## Verificación

```powershell
pnpm build
```

La implementación fue validada en navegador a 1536 × 1024 y 390 × 844 píxeles.
