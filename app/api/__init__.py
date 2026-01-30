"""FastAPI REST API for X Spaces Downloader."""

from fastapi import APIRouter

from .routes import router as main_router
from .subscription_routes import router as subscription_router
from .batch_routes import router as batch_router
from .schedule_routes import router as schedule_router
from .webhook_routes import router as webhook_router
from .annotation_routes import router as annotation_router
from .storage_routes import router as storage_router
from .cloud_routes import router as cloud_router
from .ai_settings_routes import router as ai_settings_router
from .translation_routes import router as translation_router

# Create combined router
router = APIRouter()
router.include_router(main_router)
router.include_router(subscription_router)
router.include_router(batch_router)
router.include_router(schedule_router)
router.include_router(webhook_router)
router.include_router(annotation_router)
router.include_router(storage_router)
router.include_router(cloud_router)
router.include_router(ai_settings_router)
router.include_router(translation_router)

__all__ = ["router"]
