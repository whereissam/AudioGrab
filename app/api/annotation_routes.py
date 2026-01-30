"""API routes for collaborative annotations with WebSocket support."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from .auth import verify_api_key
from .schemas import (
    CreateAnnotationRequest,
    UpdateAnnotationRequest,
    AnnotationResponse,
)
from ..core.job_store import get_job_store
from ..core.websocket_manager import get_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["annotations"], dependencies=[Depends(verify_api_key)])


def _annotation_to_response(annotation: dict, include_replies: bool = False) -> AnnotationResponse:
    """Convert annotation dict to response model."""
    replies = []
    if include_replies and "replies" in annotation:
        replies = [_annotation_to_response(r) for r in annotation["replies"]]

    return AnnotationResponse(
        id=annotation["id"],
        job_id=annotation["job_id"],
        content=annotation["content"],
        user_id=annotation["user_id"],
        user_name=annotation.get("user_name"),
        segment_start=annotation.get("segment_start"),
        segment_end=annotation.get("segment_end"),
        parent_id=annotation.get("parent_id"),
        replies=replies,
        created_at=datetime.fromisoformat(annotation["created_at"]),
        updated_at=datetime.fromisoformat(annotation["updated_at"]),
    )


@router.post("/jobs/{job_id}/annotations", response_model=AnnotationResponse)
async def create_annotation(job_id: str, request: CreateAnnotationRequest):
    """
    Create a new annotation on a transcript.

    Annotations can be attached to specific time ranges in the transcript
    or be general comments on the entire content.
    """
    job_store = get_job_store()

    # Verify job exists
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    annotation_id = str(uuid.uuid4())

    annotation = job_store.create_annotation(
        annotation_id=annotation_id,
        job_id=job_id,
        user_id=request.user_id,
        content=request.content,
        segment_start=request.segment_start,
        segment_end=request.segment_end,
        parent_id=request.parent_id,
        user_name=request.user_name,
    )

    # Broadcast to WebSocket subscribers
    ws_manager = get_websocket_manager()
    await ws_manager.broadcast_annotation_created(job_id, annotation)

    return _annotation_to_response(annotation)


@router.get("/jobs/{job_id}/annotations")
async def list_annotations(
    job_id: str,
    segment_start: Optional[float] = None,
    segment_end: Optional[float] = None,
):
    """
    List all annotations for a job.

    Optionally filter by time range to get annotations for a specific
    segment of the transcript.
    """
    job_store = get_job_store()

    # Verify job exists
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    annotations = job_store.get_annotations_for_job(
        job_id,
        segment_start=segment_start,
        segment_end=segment_end,
    )

    # Include replies for each annotation
    result = []
    for annotation in annotations:
        annotation["replies"] = job_store.get_annotation_replies(annotation["id"])
        result.append(_annotation_to_response(annotation, include_replies=True))

    return {
        "job_id": job_id,
        "annotations": [a.model_dump() for a in result],
        "total": len(result),
    }


@router.get("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(annotation_id: str):
    """Get a specific annotation with its replies."""
    job_store = get_job_store()

    annotation = job_store.get_annotation_with_replies(annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    return _annotation_to_response(annotation, include_replies=True)


@router.put("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(annotation_id: str, request: UpdateAnnotationRequest):
    """Update an annotation's content."""
    job_store = get_job_store()

    # Get existing annotation for job_id
    existing = job_store.get_annotation(annotation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Annotation not found")

    annotation = job_store.update_annotation(annotation_id, request.content)

    # Broadcast update to WebSocket subscribers
    ws_manager = get_websocket_manager()
    await ws_manager.broadcast_annotation_updated(existing["job_id"], annotation)

    return _annotation_to_response(annotation)


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str):
    """Delete an annotation and its replies."""
    job_store = get_job_store()

    # Get existing annotation for job_id
    existing = job_store.get_annotation(annotation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Annotation not found")

    job_id = existing["job_id"]
    success = job_store.delete_annotation(annotation_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete annotation")

    # Broadcast deletion to WebSocket subscribers
    ws_manager = get_websocket_manager()
    await ws_manager.broadcast_annotation_deleted(job_id, annotation_id)

    return {
        "annotation_id": annotation_id,
        "status": "deleted",
    }


@router.post("/annotations/{annotation_id}/reply", response_model=AnnotationResponse)
async def reply_to_annotation(annotation_id: str, request: CreateAnnotationRequest):
    """
    Reply to an existing annotation.

    The reply inherits the parent's job_id and optionally its time range.
    """
    job_store = get_job_store()

    # Get parent annotation
    parent = job_store.get_annotation(annotation_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent annotation not found")

    reply_id = str(uuid.uuid4())

    # Use parent's time range if not specified
    segment_start = request.segment_start
    segment_end = request.segment_end
    if segment_start is None:
        segment_start = parent.get("segment_start")
    if segment_end is None:
        segment_end = parent.get("segment_end")

    annotation = job_store.create_annotation(
        annotation_id=reply_id,
        job_id=parent["job_id"],
        user_id=request.user_id,
        content=request.content,
        segment_start=segment_start,
        segment_end=segment_end,
        parent_id=annotation_id,
        user_name=request.user_name,
    )

    # Broadcast to WebSocket subscribers
    ws_manager = get_websocket_manager()
    await ws_manager.broadcast_annotation_created(parent["job_id"], annotation)

    return _annotation_to_response(annotation)


# WebSocket endpoint for real-time updates
# Note: This endpoint doesn't use Depends(verify_api_key) because WebSocket
# authentication is handled differently
@router.websocket("/jobs/{job_id}/annotations/ws")
async def annotation_websocket(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time annotation updates.

    Clients receive messages when annotations are created, updated, or deleted.

    Message format:
    {
        "type": "annotation_created|annotation_updated|annotation_deleted",
        "annotation": {...} | null,
        "annotation_id": "..." (only for deleted)
    }
    """
    job_store = get_job_store()

    # Verify job exists
    job = job_store.get_job(job_id)
    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    ws_manager = get_websocket_manager()

    await ws_manager.connect(websocket, job_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "job_id": job_id,
            "message": "Connected to annotation updates",
        })

        # Keep connection alive and wait for disconnect
        while True:
            # Wait for any message (ping/pong or commands)
            data = await websocket.receive_text()

            # Handle ping
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket, job_id)
