# Bibliotecario virtual con RAG

## Objetivo

Responder preguntas sobre el catálogo utilizando únicamente información recuperada desde PostgreSQL. Cada respuesta conserva fuentes, memoria conversacional y consumo de tokens.

## Flujo de indexación

1. Un administrador selecciona un libro.
2. El backend combina título, autores, géneros, editorial, año, ISBN y sinopsis.
3. El texto se normaliza y divide en fragmentos solapados.
4. El proveedor genera un embedding de 1536 dimensiones por fragmento.
5. PostgreSQL almacena el documento, los fragmentos y los vectores.
6. Un hash evita regenerar embeddings cuando el contenido no cambió.

Endpoint:

```text
POST /api/v1/rag/books/{book_id}/index
```

Operaciones administrativas adicionales:

```text
GET  /api/v1/rag/books/status
POST /api/v1/rag/books/index-all
```

Los cambios en libros, autores, géneros o editoriales marcan el documento relacionado como
desactualizado y lo excluyen de las consultas hasta volver a indexarlo.

Los administradores también pueden gestionar textos internos independientes del catálogo:

```text
GET    /api/v1/rag/documents
POST   /api/v1/rag/documents
PUT    /api/v1/rag/documents/{document_id}
DELETE /api/v1/rag/documents/{document_id}
```

## Flujo de consulta

1. Se verifica que el servicio esté activo y que el usuario tenga saldo.
2. Se genera el embedding de la pregunta.
3. pgvector recupera los fragmentos más cercanos mediante distancia coseno.
4. Se agrega una memoria breve de los últimos mensajes.
5. Gemini genera una respuesta limitada al contexto recuperado.
6. La conversación, respuesta, fuentes y tokens se guardan en PostgreSQL.

Endpoint:

```text
POST /api/v1/ai/chat
```

Ejemplo:

```json
{
  "question": "¿Qué temas aborda Frankenstein?",
  "conversation_id": null,
  "top_k": 5
}
```

Para continuar la memoria se envía el `conversation_id` devuelto por la primera respuesta.

## Seguridad y calidad

- La clave del proveedor existe únicamente en `.env` y en el contenedor backend.
- El frontend nunca recibe la clave.
- Las respuestas deben citar `[Fuente N]` y declarar falta de información.
- La aplicación conserva la conversación en PostgreSQL y no envía historial innecesario.
- El proveedor se abstrae detrás de una interfaz para permitir cambios sin afectar las rutas.
- Las pruebas utilizan lógica local y no consumen la API.

## Configuración

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=...
AI_CHAT_MODEL=gemini-3.8-flash
AI_EMBEDDING_MODEL=gemini-embedding-001
AI_EMBEDDING_DIMENSIONS=1536
AI_RETRY_ATTEMPTS=3
AI_RETRY_BACKOFF_SECONDS=1
RAG_CHUNK_SIZE=1800
RAG_CHUNK_OVERLAP=200
RAG_TOP_K=5
```

La dimensión no puede cambiarse sin migrar la columna vectorial y reconstruir el índice.

Gemini usa tipos de tarea distintos para indexar documentos (`RETRIEVAL_DOCUMENT`) y
consultar (`RETRIEVAL_QUERY`). El adaptador de OpenAI permanece disponible como alternativa
configurando `AI_PROVIDER=openai`, `AI_API_KEY` y sus modelos correspondientes.

Los errores transitorios `429`, `500`, `502`, `503` y `504` de Gemini se reintentan con
espera exponencial. Si persisten, la API devuelve `503 Service Unavailable` con un mensaje seguro.
