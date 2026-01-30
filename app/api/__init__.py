"""FastAPI REST API for X Spaces Downloader."""

from fastapi import APIRouter

from .routes import router as main_router
from .subscription_routes import router as subscription_router

# Create combined router
router = APIRouter()
router.include_router(main_router)
router.include_router(subscription_router)

__all__ = ["router"]
