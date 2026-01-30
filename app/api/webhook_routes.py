"""API routes for webhook configuration and testing."""

import logging

from fastapi import APIRouter, Depends

from .auth import verify_api_key
from .schemas import (
    WebhookConfig,
    WebhookTestRequest,
    WebhookTestResponse,
)
from ..config import get_settings
from ..core.webhook_notifier import get_webhook_notifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"], dependencies=[Depends(verify_api_key)])


@router.get("/config", response_model=WebhookConfig)
async def get_webhook_config():
    """Get current webhook configuration."""
    settings = get_settings()

    return WebhookConfig(
        default_url=settings.default_webhook_url,
        retry_attempts=settings.webhook_retry_attempts,
        retry_delay=settings.webhook_retry_delay,
    )


@router.post("/test", response_model=WebhookTestResponse)
async def test_webhook(request: WebhookTestRequest):
    """
    Send a test webhook to verify the URL is working.

    Returns success/failure and any error message.
    """
    notifier = get_webhook_notifier()
    success, error = await notifier.send_test(request.url)

    return WebhookTestResponse(
        success=success,
        error=error,
    )


@router.get("/events")
async def list_webhook_events():
    """List all webhook event types and their payload formats."""
    return {
        "events": [
            {
                "event": "job_completed",
                "description": "Fired when a download or transcription job completes successfully",
                "payload": {
                    "event": "job_completed",
                    "job_id": "string",
                    "status": "completed",
                    "job_type": "download|transcribe",
                    "content_info": "object|null",
                    "file_path": "string|null",
                    "file_size_mb": "number|null",
                    "error": "null",
                    "batch_id": "string|null",
                    "timestamp": "ISO datetime",
                },
            },
            {
                "event": "job_failed",
                "description": "Fired when a download or transcription job fails",
                "payload": {
                    "event": "job_failed",
                    "job_id": "string",
                    "status": "failed",
                    "job_type": "download|transcribe",
                    "content_info": "object|null",
                    "file_path": "null",
                    "file_size_mb": "null",
                    "error": "string",
                    "batch_id": "string|null",
                    "timestamp": "ISO datetime",
                },
            },
            {
                "event": "batch_completed",
                "description": "Fired when all jobs in a batch have finished",
                "payload": {
                    "event": "batch_completed",
                    "batch_id": "string",
                    "name": "string|null",
                    "status": "completed|completed_with_errors",
                    "total_jobs": "number",
                    "completed_jobs": "number",
                    "failed_jobs": "number",
                    "timestamp": "ISO datetime",
                },
            },
            {
                "event": "test",
                "description": "Test event sent via /api/webhooks/test endpoint",
                "payload": {
                    "event": "test",
                    "message": "string",
                    "timestamp": "ISO datetime",
                },
            },
        ],
    }
