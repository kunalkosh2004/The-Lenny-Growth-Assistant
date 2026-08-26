from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.artifacts import router as artifacts_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.api.providers import router as providers_router
from app.api.sessions import router as sessions_router
from app.api.skills import router as skills_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="The Lenny Growth Assistant API",
        version="0.1.0",
        description="Grounded AI assistant backend for Lenny's Podcast transcripts.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(artifacts_router)
    app.include_router(chat_router)
    app.include_router(knowledge_router)
    app.include_router(providers_router)
    app.include_router(sessions_router)
    app.include_router(skills_router)
    return app


app = create_app()
