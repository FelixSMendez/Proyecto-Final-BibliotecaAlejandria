# Migraciones

El esquema inicial se instala desde `../database/001_initial_schema.sql` porque también es un entregable explícito del proyecto.

Después de instalarlo, Alembic administrará los cambios incrementales:

```bash
uv run alembic revision --autogenerate -m "descripcion del cambio"
uv run alembic upgrade head
```

No debe generarse una migración inicial sobre una base vacía hasta decidir si el script SQL será importado como revisión base. Esto evita mantener dos definiciones iniciales divergentes.
