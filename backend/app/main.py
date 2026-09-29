import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.app.ai.providers import LessonProvider, configured_provider
from backend.app.api import admin_routes, assessment_routes, auth_routes, graph_routes, learning_routes, video_routes
from backend.app.core.config import settings
from backend.app.core.database import Base, create_database
import backend.app.models
from backend.app.video.adapter import ExistingPipelineAdapter, VideoAdapter

logger = logging.getLogger("wh_backend")


def create_app(
    database_url: str | None = None,
    lesson_provider: LessonProvider | None = None,
    video_adapter: VideoAdapter | None = None,
    initialize_database: bool = True,
) -> FastAPI:
    if settings.environment != "development" and (
        settings.jwt_secret == "development-only-change-me" or len(settings.jwt_secret) < 32
    ):
        raise RuntimeError("Set WH_JWT_SECRET to a random secret of at least 32 characters outside development")
    engine, factory = create_database(database_url or settings.database_url)
    if initialize_database:
        Base.metadata.create_all(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        engine.dispose()

    application = FastAPI(
        title="WH Education API",
        version="1.0.0",
        description="Authenticated API for lessons, learning paths, knowledge graphs, assessment, progress, and video jobs.",
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.state.session_factory = factory
    application.state.lesson_provider = lesson_provider or configured_provider()
    application.state.video_adapter = video_adapter or ExistingPipelineAdapter()
    origins = settings.cors_origins
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    application.include_router(auth_routes.router, prefix="/api/v1")
    application.include_router(admin_routes.router, prefix="/api/v1")
    application.include_router(learning_routes.router, prefix="/api/v1")
    application.include_router(graph_routes.router, prefix="/api/v1")
    application.include_router(assessment_routes.router, prefix="/api/v1")
    application.include_router(video_routes.router, prefix="/api/v1")

    @application.get("/api/v1/health", tags=["health"])
    def health():
        try:
            with factory() as session:
                session.execute(text("SELECT 1"))
        except Exception as exc:
            logger.exception("Database health check failed")
            return {"status": "unhealthy", "database": "unavailable", "detail": type(exc).__name__}
        return {"status": "ok", "database": "ok", "ai_provider": type(application.state.lesson_provider).__name__}

    return application


app = create_app()
