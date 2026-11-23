"""Health-check endpoint for the CricketBowlingCoach API."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return the current health status of the API."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }
