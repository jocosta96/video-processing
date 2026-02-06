from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import auth_router, health_router, jobs_router, videos_router
from src.core.config import settings
from src.services import StorageService

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    storage = StorageService()
    storage.ensure_bucket_exists()
    yield


app = FastAPI(
    title="FIAP X - Video Processing API",
    description="""
## Sistema de Processamento de Videos

API para upload de videos, extracao de frames e download de arquivos ZIP.

### Funcionalidades

* **Autenticacao** - Registro, login com JWT
* **Upload** - Envio de videos para processamento
* **Status** - Acompanhamento do processamento
* **Download** - URL assinada para baixar frames

### Fluxo

1. Registre um usuario em `/auth/register`
2. Faca login em `/auth/login` para obter o token
3. Use o token no header `Authorization: Bearer {token}`
4. Envie um video em `/videos/upload`
5. Acompanhe o status em `/videos/{id}`
6. Baixe o ZIP em `/jobs/{id}/download`

### Formatos Suportados

`.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.flv`, `.webm`
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Health", "description": "Health check endpoints"},
        {"name": "Authentication", "description": "Registro e login de usuarios"},
        {"name": "Videos", "description": "Upload e listagem de videos"},
        {"name": "Jobs", "description": "Status e download de jobs processados"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health_router)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(videos_router, prefix=settings.api_prefix)
app.include_router(jobs_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {"service": "fiapx-api", "version": "1.0.0", "docs": "/docs"}
