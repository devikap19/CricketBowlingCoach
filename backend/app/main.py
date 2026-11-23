"""CricketBowlingCoach API — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.api.quality import router as quality_router
from app.api.pose import router as pose_router
from app.api.tracking import router as tracking_router
from app.api.coaching import router as coaching_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Cricket bowling analysis and coaching API.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware for frontend communication
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    application.include_router(health_router, prefix="/api", tags=["Health"])
    application.include_router(sessions_router, prefix="/api", tags=["Sessions"])
    application.include_router(quality_router, prefix="/api", tags=["Video Quality"])
    application.include_router(pose_router, prefix="/api", tags=["Pose Assessment"])
    application.include_router(tracking_router, prefix="/api", tags=["Subject Tracking"])
    application.include_router(coaching_router, prefix="/api", tags=["Coach Feedback & Reports"])

    return application


app = create_app()
