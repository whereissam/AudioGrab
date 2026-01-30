"""FastAPI application entry point."""

import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    logger.info("Starting AudioGrab API")
    logger.info(f"Auth configured: {settings.has_auth}")
    logger.info(f"Download directory: {settings.download_dir}")

    # Recover unfinished jobs from previous run
    try:
        from .core.workflow import recover_unfinished_jobs
        from .core.job_store import get_job_store

        job_store = get_job_store()
        unfinished = job_store.get_unfinished_jobs()
        if unfinished:
            logger.info(f"Found {len(unfinished)} unfinished jobs - will recover in background")
            # Don't await - let it run in background so server starts quickly
            import asyncio
            asyncio.create_task(recover_unfinished_jobs())
    except Exception as e:
        logger.error(f"Failed to start job recovery: {e}")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down AudioGrab API")
    try:
        from .core.job_store import get_job_store
        job_store = get_job_store()
        job_store.cleanup_old_jobs(days=7)
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


app = FastAPI(
    title="AudioGrab API",
    description="API for downloading audio from X Spaces, Apple Podcasts, and Spotify",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api", tags=["download"])


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "AudioGrab API",
        "version": "0.2.0",
        "docs": "/docs",
        "health": "/api/health",
        "audio": ["x_spaces", "apple_podcasts", "spotify", "youtube", "xiaoyuzhou"],
        "video": ["x_video", "youtube_video"],
    }


def main():
    """Run the application with uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
