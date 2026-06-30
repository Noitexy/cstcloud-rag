from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_chat,
    routes_config,
    routes_conversations,
    routes_documents,
    routes_eval,
    routes_knowledge_base,
    routes_models,
    routes_retrieval,
)
from app.clients.cstcloud_client import CSTCloudAPIError
from app.core.config import get_settings
from app.core.security import api_key_configured
from app.models.db import init_db
from app.utils.logger import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_directories()
    init_db()
    logger.info("Application started: api_key_configured=%s", api_key_configured())
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于中国科技云 OpenAI-Compatible API 的企业级混合检索 RAG 服务",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(CSTCloudAPIError)
async def cstcloud_error_handler(_: Request, exc: CSTCloudAPIError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/api/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "api_key_configured": api_key_configured(),
    }


for router in (
    routes_models.router,
    routes_config.router,
    routes_knowledge_base.router,
    routes_documents.router,
    routes_retrieval.router,
    routes_chat.router,
    routes_conversations.router,
    routes_eval.router,
):
    app.include_router(router, prefix=settings.api_prefix)
