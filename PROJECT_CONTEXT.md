# Contexto del proyecto: La Biblioteca de Alejandría

## Propósito de este archivo

Este documento conserva las decisiones funcionales y técnicas del proyecto final de Programación Comercial. Debe actualizarse cuando cambie el alcance, la arquitectura o una decisión importante. Su objetivo es que cualquier integrante o asistente pueda retomar el proyecto sin perder contexto.

## Identidad del proyecto

- **Nombre:** La Biblioteca de Alejandría
- **Tipo:** Aplicación web de consulta, descubrimiento e investigación de libros asistida por inteligencia artificial.
- **Objetivo:** Permitir que usuarios registrados consulten un catálogo propio, conversen con un asistente basado en RAG, reciban recomendaciones razonadas e investiguen autores, obras y temas utilizando fuentes internas y externas.
- **Usuarios:** Lectores, estudiantes e investigadores casuales.
- **Roles:** Usuario y administrador.

## Propuesta de valor

La aplicación centraliza un catálogo administrable de libros y utiliza inteligencia artificial para convertirlo en una experiencia de consulta conversacional. No se limita a responder preguntas: también compara opciones, investiga información externa y explica las fuentes utilizadas.

## Alcance funcional

### Usuario

- Registrarse e iniciar/cerrar sesión.
- Consultar y buscar libros del catálogo.
- Usar los tres servicios de IA.
- Revisar su historial de conversaciones.
- Consultar su consumo y límite de tokens.
- Guardar recomendaciones o listas de lectura, si el tiempo de desarrollo lo permite.

### Administrador

- Gestionar usuarios y roles.
- Crear, editar, consultar y desactivar libros, autores, géneros y editoriales.
- Cargar o administrar los textos y metadatos que alimentan el RAG.
- Activar o desactivar servicios de IA.
- Configurar límites de tokens por usuario.
- Consultar reportes globales con filtros por usuario, fecha y servicio.

## Servicios de inteligencia artificial

### 1. Bibliotecario virtual con RAG

Servicio principal. Responde preguntas utilizando únicamente información recuperada del catálogo y los documentos internos.

Ejemplos:

- ¿Qué libros de ciencia ficción latinoamericana tiene la biblioteca?
- ¿Cuál es la temática principal de este libro?
- ¿Qué obras disponibles pertenecen al realismo mágico?
- Compara los libros disponibles de dos autores.

Flujo:

1. Recibir la pregunta.
2. Generar su embedding.
3. Recuperar fragmentos relevantes desde PostgreSQL con pgvector.
4. Construir el contexto con metadatos y fuentes.
5. Generar una respuesta con referencias a los libros utilizados.
6. Indicar claramente cuando la información disponible sea insuficiente.
7. Registrar conversación, fuentes, tokens y tiempo de ejecución.

### 2. Agente recomendador de lecturas

Interpreta preferencias y ejecuta varios pasos para recomendar libros.

Datos posibles: géneros, autores, temas, extensión, idioma, época, nivel de dificultad y libros previamente valorados.

Flujo:

1. Interpretar la solicitud y detectar criterios faltantes.
2. Buscar candidatos en el catálogo.
3. Consultar características y disponibilidad.
4. Obtener información externa cuando sea necesario.
5. Comparar y puntuar candidatos.
6. Presentar una recomendación explicada, con ventajas y posibles limitaciones.

### 3. Agente de investigación literaria

Investiga un autor, obra, corriente o tema mediante varias consultas y entrega un resumen con fuentes.

Flujo:

1. Dividir la pregunta en datos necesarios.
2. Consultar el catálogo interno.
3. Consultar fuentes externas autorizadas.
4. Contrastar autores, fechas, ediciones o contexto histórico.
5. Detectar contradicciones o falta de información.
6. Elaborar un resumen estructurado con enlaces y fuentes.

Fuentes externas candidatas: Open Library, Google Books y Wikipedia/Wikidata. Antes de implementar se elegirá el conjunto mínimo necesario y se revisarán sus condiciones de uso.

## Arquitectura aprobada

Se utilizará un **monolito modular**: un frontend independiente y una API backend modular, ambos en el mismo repositorio. No se usarán microservicios.

```text
React + TypeScript
        |
        | HTTPS + JWT
        v
FastAPI
  |-- autenticación y roles
  |-- CRUD administrativo
  |-- chatbot RAG
  |-- agentes y herramientas
  |-- historial y tokens
  |-- endpoints para Power BI
        |
        +--> PostgreSQL + pgvector
        +--> proveedor de IA
        +--> APIs externas de libros

Power BI --> API REST de reportes
```

### Principios

- El frontend nunca accede directamente a la base de datos.
- Las claves y secretos existen únicamente en variables de entorno del backend.
- Toda operación protegida valida el JWT, rol y límite de tokens.
- Los servicios de IA se implementan detrás de interfaces para poder cambiar de proveedor.
- Las respuestas del RAG deben conservar las fuentes recuperadas.
- Las consultas externas deben registrar su origen y fecha.
- Los endpoints para Power BI son de solo lectura y requieren autenticación.

## Tecnologías seleccionadas

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- TanStack Query para llamadas y caché de la API
- React Hook Form y Zod para formularios
- Recharts para reportes web

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic para migraciones
- JWT para sesiones
- Argon2 para contraseñas
- Cliente oficial del proveedor de IA
- HTTPX para servicios externos

### Datos e IA

- PostgreSQL como base operacional y analítica del proyecto
- pgvector para embeddings y búsqueda semántica
- RAG implementado en la capa de servicios del backend
- Uso directo del SDK del proveedor de IA; no agregar LangChain inicialmente
- Modelo de chat y modelo de embeddings configurables mediante variables de entorno

### Calidad, entrega y despliegue

- Pytest para pruebas del backend
- Vitest para pruebas puntuales del frontend, si el tiempo lo permite
- Docker y Docker Compose para desarrollo local
- GitHub Actions para CI/CD
- Swagger/OpenAPI generado por FastAPI
- Vercel para frontend
- Render para backend
- Supabase para PostgreSQL con pgvector
- Power BI Desktop para el archivo de reporte

## Modelo de datos preliminar

### Seguridad y configuración

- `users`: identidad, contraseña cifrada, rol, estado y fechas.
- `user_token_limits`: límite, periodo y consumo acumulado.
- `ai_services`: nombre, tipo, configuración pública, estado y límite predeterminado.

### Dominio de biblioteca

- `authors`: autores y datos biográficos básicos.
- `publishers`: editoriales.
- `genres`: géneros o categorías.
- `books`: ISBN, título, sinopsis, año, idioma, páginas, portada, estado y editorial.
- `book_authors`: relación entre libros y autores.
- `book_genres`: relación entre libros y géneros.
- `book_copies`: ejemplares y disponibilidad, opcional para el MVP.
- `reading_lists`: listas guardadas por los usuarios, opcional.
- `reading_list_items`: libros de una lista, opcional.

### RAG, conversaciones y auditoría

- `documents`: documento fuente asociado o no a un libro.
- `document_chunks`: fragmento, embedding y metadatos de origen.
- `conversations`: conversación, usuario, servicio y fechas.
- `messages`: rol, contenido, fuentes y tokens.
- `service_executions`: servicio, usuario, modelo, tokens, duración, estado y error.
- `external_sources`: URL, proveedor, fecha de consulta y metadatos.

## API preliminar

```text
POST   /api/v1/auth/login
GET    /api/v1/auth/me

GET    /api/v1/users
POST   /api/v1/users
PUT    /api/v1/users/{id}
DELETE /api/v1/users/{id}

GET    /api/v1/books
POST   /api/v1/books
GET    /api/v1/books/{id}
PUT    /api/v1/books/{id}
DELETE /api/v1/books/{id}

GET    /api/v1/authors
POST   /api/v1/authors
GET    /api/v1/genres
POST   /api/v1/genres

POST   /api/v1/ai/chat
POST   /api/v1/ai/recommend
POST   /api/v1/ai/research

GET    /api/v1/history
GET    /api/v1/usage/me
GET    /api/v1/reports/usage
GET    /api/v1/reports/conversations
```

## Reportes

La aplicación web y Power BI deben mostrar información coincidente.

Métricas mínimas:

- Cantidad de consultas por fecha.
- Consultas por servicio.
- Tokens consumidos por servicio.
- Tokens consumidos por usuario.
- Usuarios con mayor uso.
- Ejecuciones satisfactorias y fallidas.
- Tiempo promedio de respuesta, si se alcanza a implementar.

Power BI consumirá endpoints REST de solo lectura que devuelvan JSON tabular y acepten filtros de fecha y servicio.

## Pruebas mínimas obligatorias

- Login correcto e incorrecto.
- Autorización por rol.
- Bloqueo al alcanzar el límite de tokens.
- CRUD principal de libros.
- Registro y consulta del historial.
- Cálculo y acumulación de consumo.
- Recuperación de contexto del RAG.
- Respuesta cuando el RAG no encuentra información suficiente.
- Ejecución satisfactoria de cada agente con servicios externos simulados.

Las pruebas no deben depender de llamadas reales a proveedores de IA ni APIs externas; se usarán mocks o adaptadores falsos.

## Estructura prevista del repositorio

```text
Proyecto_FInal_PrograComer/
|-- frontend/
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- core/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- repositories/
|   |   |-- services/
|   |   |-- rag/
|   |   `-- agents/
|   |-- migrations/
|   `-- tests/
|-- database/
|   |-- schema.sql
|   `-- seed.sql
|-- powerbi/
|-- docs/
|-- .github/workflows/
|-- compose.yml
|-- .env.example
|-- README.md
`-- PROJECT_CONTEXT.md
```

## Alcance del MVP

Debe estar terminado antes de agregar funciones opcionales:

1. Autenticación con roles.
2. CRUD de usuarios, libros, autores y géneros.
3. Catálogo web.
4. Chatbot RAG con fuentes.
5. Agente recomendador.
6. Agente de investigación.
7. Historial y control de tokens.
8. Reporte web.
9. Endpoints y archivo de Power BI.
10. Pruebas automatizadas, Swagger, CI/CD y despliegue.

Quedan fuera del MVP: préstamos reales, pagos, notificaciones, chat en tiempo real, microservicios, Redis, Kafka, Kubernetes y una base vectorial separada.

## Decisiones confirmadas

- El producto se manejará inicialmente como catálogo digital; préstamos y ejemplares quedan fuera del MVP.
- La autenticación tendrá access tokens JWT y refresh tokens revocables.
- Los usuarios creados o modificados por la aplicación usarán Argon2; las cuentas semilla bcrypt serán compatibles durante desarrollo.
- El catálogo admite múltiples autores, colaboradores y géneros por libro.
- La primera migración de datos vive en `database/001_initial_schema.sql` y los datos demostrativos en `database/002_seed_data.sql`.
- El adaptador predeterminado utiliza Google Gen AI SDK con Gemini; OpenAI queda disponible
  como proveedor alternativo mediante configuración.
- Los embeddings iniciales usan 1536 dimensiones y se almacenan en PostgreSQL con pgvector.
- El proveedor permanece detrás de una interfaz para permitir sustitución futura.

## Decisiones pendientes

- Confirmar presupuesto y límites operativos de Gemini antes del despliegue productivo.
- Definir el volumen y origen de los datos iniciales.
- Confirmar si la identidad visual editorial requiere una marca registrada antes del despliegue público.

## Decisiones adicionales confirmadas

- Los usuarios del MVP son creados por el administrador; no habrá registro público inicial.
- La investigación utiliza Open Library y Wikipedia mediante MediaWiki como fuentes externas.
- Los cambios bibliográficos invalidan el documento vectorial hasta su nueva indexación.

## Regla de actualización

Toda decisión que cambie el alcance, las tecnologías, los servicios de IA, el modelo de datos o el despliegue debe registrarse aquí antes o al mismo tiempo que se implementa.

## Convención de documentación del código

- Todo módulo nuevo debe incluir un docstring breve que explique su responsabilidad.
- Las funciones públicas, reglas de negocio y endpoints deben tener docstrings profesionales y concisos.
- Los comentarios se reservan para decisiones de seguridad, persistencia, compatibilidad o lógica que no resulte evidente.
- No se comentarán instrucciones triviales ni se duplicará literalmente lo que ya expresa el código.
- Esta convención aplica a todo código generado a partir de este punto.

## Estado de implementación

- Estructura del repositorio creada.
- Esquema inicial y datos semilla disponibles en `database/`.
- Backend FastAPI inicial implementado.
- Autenticación con access token, refresh token rotatorio y cierre de sesión implementada.
- Administración de usuarios con roles y desactivación lógica implementada.
- CRUD de libros, autores, géneros y editoriales implementado.
- Migración Alembic de servicios de IA, conversaciones, mensajes y ejecuciones aplicada.
- Historial personal y consulta detallada de conversaciones implementados.
- Reinicio mensual, validación de límites y acumulación de tokens implementados.
- Reporte administrativo de consumo con filtros por usuario, servicio y fechas implementado.
- Migración `0002_rag_documents` aplicada con documentos, fragmentos e índice vectorial HNSW.
- Indexación de libros, recuperación semántica, memoria conversacional y respuestas con fuentes implementadas.
- El RAG registra tokens, ejecuciones exitosas o fallidas e historial en PostgreSQL.
- Swagger/OpenAPI disponible automáticamente.
- Pruebas unitarias iniciales y flujo de CI del backend implementados.
- Gemini configurado como proveedor predeterminado con reintentos ante saturación temporal.
- Recomendador de lecturas implementado con filtros, puntuación y explicación sustentada.
- Investigador literario implementado con catálogo, Open Library, Wikipedia y auditoría de fuentes.
- Estado e indexación masiva del catálogo implementados; los cambios invalidan vectores antiguos.
- Gestión e indexación de documentos internos independientes del catálogo implementada.
- Migración `0004_execution_model` registra el modelo utilizado por cada ejecución.
- Reportes de conversaciones, resumen global, tokens y duración implementados para Power BI.
- Frontend React + TypeScript implementado con autenticación, catálogo, RAG, recomendación,
  investigación, historial y panel administrativo.
- Identidad visual confirmada: biblioteca antigua editorial con papel marfil, nogal, verde bosque,
  latón, Cormorant Garamond para títulos y Manrope para controles.
- El frontend cuenta con diseño adaptable, activos visuales locales, build de producción y servicio
  Nginx integrado en `compose.yml`.
- La migración `0005_extended_catalog_seed` amplía el catálogo a 120 obras canónicas, 56 autores
  y 15 géneros mediante identidades estables, carga idempotente y datos independientes de edición.
- La indexación RAG procesa únicamente documentos pendientes o desactualizados en lotes configurables;
  recomendación conserva obras sin paginación conocida y Gemini reserva su salida para texto visible.
- Archivo de Power BI y despliegue productivo pendientes.
