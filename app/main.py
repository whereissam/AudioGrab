"""FastAPI application entry point."""

import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .api import router as api_router
from .api.ratelimit import limiter
from .api.middleware import TimeoutMiddleware, RequestIDMiddleware
from .logging_config import configure_logging, get_logger

# Configure structured logging
_settings = get_settings()
configure_logging(json_logs=not _settings.debug, log_level="DEBUG" if _settings.debug else "INFO")
logger = get_logger(__name__)

# Initialize Sentry if configured
if _settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_settings.sentry_dsn,
        environment=_settings.sentry_environment,
        traces_sample_rate=_settings.sentry_traces_sample_rate,
        send_default_pii=False,  # Don't send PII
    )
    logger.info("sentry_initialized", environment=_settings.sentry_environment)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    logger.info("Starting AudioGrab API")
    logger.info(f"Server: {settings.host}:{settings.port}")
    logger.info(f"API auth: {'enabled (X-API-Key required)' if settings.api_key else 'disabled (open access)'}")
    logger.info(f"Twitter auth: {settings.has_auth}")
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

    # Start subscription worker
    try:
        from .core.subscription_worker import start_subscription_worker
        await start_subscription_worker()
    except Exception as e:
        logger.error(f"Failed to start subscription worker: {e}")

    yield

    # Stop subscription worker
    try:
        from .core.subscription_worker import stop_subscription_worker
        await stop_subscription_worker()
    except Exception as e:
        logger.error(f"Failed to stop subscription worker: {e}")

    # Cleanup on shutdown
    logger.info("Shutting down AudioGrab API")
    try:
        from .core.job_store import get_job_store
        from .core.checkpoint import CheckpointManager

        job_store = get_job_store()
        checkpoint_manager = CheckpointManager()

        # Clean up old data
        jobs_deleted = job_store.cleanup_old_jobs(days=7)
        checkpoints_deleted = checkpoint_manager.cleanup_old_checkpoints(max_age_hours=24)

        if jobs_deleted or checkpoints_deleted:
            logger.info(f"Cleanup: {jobs_deleted} old jobs, {checkpoints_deleted} old checkpoints")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


app = FastAPI(
    title="AudioGrab API",
    description="API for downloading audio from X Spaces, Apple Podcasts, and Spotify",
    version="0.2.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
_settings = get_settings()
_cors_origins = (
    ["*"] if _settings.cors_origins == "*"
    else [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)

# Timeout middleware
app.add_middleware(TimeoutMiddleware)

# Request ID middleware (for tracing)
app.add_middleware(RequestIDMiddleware)

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
