"""FastAPI REST API for X Spaces Downloader."""

from fastapi import APIRouter

from .routes import router as main_router
from .subscription_routes import router as subscription_router
from .batch_routes import router as batch_router
from .schedule_routes import router as schedule_router
from .webhook_routes import router as webhook_router
from .annotation_routes import router as annotation_router

# Create combined router
router = APIRouter()
router.include_router(main_router)
router.include_router(subscription_router)
router.include_router(batch_router)
router.include_router(schedule_router)
router.include_router(webhook_router)
router.include_router(annotation_router)

__all__ = ["router"]
