# EndPoint Cloud Security — Final project

Banking REST API built with FastAPI, PostgreSQL, Nginx and Docker Compose.


## Run the API

```bash
poetry run uvicorn main:banking_app --reload
```

The OpenAPI documentation is available at `http://127.0.0.1:8000/mc101-docs`.

## Identifier choice

The API uses sequential integer identifiers for simplicity, UUID identifiers would be better