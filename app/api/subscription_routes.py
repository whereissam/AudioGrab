"""FastAPI routes for subscription management."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from .auth import verify_api_key
from .subscription_schemas import (
    CreateSubscriptionRequest,
    UpdateSubscriptionRequest,
    SubscriptionResponse,
    SubscriptionListResponse,
    SubscriptionItemResponse,
    SubscriptionItemListResponse,
    CheckSubscriptionResponse,
    SubscriptionType,
    SubscriptionPlatform,
    SubscriptionItemStatus,
)
from ..core.subscription_store import (
    get_subscription_store,
    SubscriptionStore,
    SubscriptionType as StoreSubscriptionType,
    SubscriptionPlatform as StorePlatform,
    SubscriptionItemStatus as StoreItemStatus,
)
from ..core.subscription_fetcher import get_fetcher

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/subscriptions",
    tags=["subscriptions"],
    dependencies=[Depends(verify_api_key)],
)


def _get_store() -> SubscriptionStore:
    """Dependency to get subscription store."""
    return get_subscription_store()


def _subscription_to_response(sub: dict, store: SubscriptionStore) -> SubscriptionResponse:
    """Convert subscription dict to response model with computed fields."""
    # Get counts
    pending_count = store.count_items(sub["id"], StoreItemStatus.PENDING)
    completed_count = store.count_items(sub["id"], StoreItemStatus.COMPLETED)

    return SubscriptionResponse(
        id=sub["id"],
        name=sub["name"],
        subscription_type=SubscriptionType(sub["subscription_type"]),
        source_url=sub.get("source_url"),
        source_id=sub.get("source_id"),
        platform=SubscriptionPlatform(sub["platform"]),
        enabled=sub.get("enabled", True),
        auto_transcribe=sub.get("auto_transcribe", False),
        transcribe_model=sub.get("transcribe_model", "base"),
        transcribe_language=sub.get("transcribe_language"),
        download_limit=sub.get("download_limit", 10),
        output_format=sub.get("output_format", "m4a"),
        quality=sub.get("quality", "high"),
        output_dir=sub.get("output_dir"),
        last_checked_at=sub.get("last_checked_at"),
        last_new_content_at=sub.get("last_new_content_at"),
        total_downloaded=sub.get("total_downloaded", 0),
        created_at=sub["created_at"],
        updated_at=sub["updated_at"],
        pending_count=pending_count,
        completed_count=completed_count,
    )


def _item_to_response(item: dict) -> SubscriptionItemResponse:
    """Convert item dict to response model."""
    return SubscriptionItemResponse(
        id=item["id"],
        subscription_id=item["subscription_id"],
        content_id=item["content_id"],
        content_url=item["content_url"],
        title=item.get("title"),
        published_at=item.get("published_at"),
        status=SubscriptionItemStatus(item["status"]),
        job_id=item.get("job_id"),
        file_path=item.get("file_path"),
        transcription_path=item.get("transcription_path"),
        error=item.get("error"),
        discovered_at=item["discovered_at"],
        downloaded_at=item.get("downloaded_at"),
    )


@router.post("", response_model=SubscriptionResponse)
async def create_subscription(
    request: CreateSubscriptionRequest,
    store: SubscriptionStore = Depends(_get_store),
):
    """
    Create a new subscription.

    Supports:
    - RSS feeds (podcasts)
    - YouTube channels
    - YouTube playlists
    """
    # Validate source URL and get metadata
    fetcher = get_fetcher(request.subscription_type.value)
    is_valid, source_id, source_name = await fetcher.validate_source(request.source_url)

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source URL for {request.subscription_type.value}",
        )

    # Determine platform
    if request.subscription_type == SubscriptionType.RSS:
        platform = StorePlatform.PODCAST
        # Use validated RSS URL (may be different from input for Apple Podcasts)
        source_url = source_id if source_id != request.source_url else request.source_url
        source_id = None
    else:
        platform = StorePlatform.YOUTUBE
        source_url = request.source_url

    # Generate subscription ID
    subscription_id = str(uuid.uuid4())

    # Create subscription
    sub = store.create_subscription(
        subscription_id=subscription_id,
        name=request.name or source_name or "Unnamed Subscription",
        subscription_type=StoreSubscriptionType(request.subscription_type.value),
        platform=platform,
        source_url=source_url,
        source_id=source_id,
        auto_transcribe=request.auto_transcribe,
        transcribe_model=request.transcribe_model,
        transcribe_language=request.transcribe_language,
        download_limit=request.download_limit,
        output_format=request.output_format,
        quality=request.quality,
        output_dir=request.output_dir,
    )

    logger.info(f"Created subscription: {subscription_id} ({request.name})")
    return _subscription_to_response(sub, store)


@router.get("", response_model=SubscriptionListResponse)
async def list_subscriptions(
    enabled_only: bool = Query(False, description="Only return enabled subscriptions"),
    platform: Optional[SubscriptionPlatform] = Query(None, description="Filter by platform"),
    store: SubscriptionStore = Depends(_get_store),
):
    """List all subscriptions."""
    store_platform = StorePlatform(platform.value) if platform else None
    subs = store.list_subscriptions(enabled_only=enabled_only, platform=store_platform)

    return SubscriptionListResponse(
        subscriptions=[_subscription_to_response(s, store) for s in subs],
        total=len(subs),
    )


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: str,
    store: SubscriptionStore = Depends(_get_store),
):
    """Get subscription details."""
    sub = store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return _subscription_to_response(sub, store)


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: str,
    request: UpdateSubscriptionRequest,
    store: SubscriptionStore = Depends(_get_store),
):
    """Update a subscription."""
    sub = store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Build update dict from non-None fields
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    if not updates:
        return _subscription_to_response(sub, store)

    updated = store.update_subscription(subscription_id, **updates)
    return _subscription_to_response(updated, store)


@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    store: SubscriptionStore = Depends(_get_store),
):
    """Delete a subscription and all its items."""
    sub = store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    store.delete_subscription(subscription_id)
    return {"status": "deleted", "subscription_id": subscription_id}


@router.post("/{subscription_id}/check", response_model=CheckSubscriptionResponse)
async def check_subscription(
    subscription_id: str,
    background_tasks: BackgroundTasks,
    store: SubscriptionStore = Depends(_get_store),
):
    """
    Force check a subscription for new content.

    This triggers an immediate check and queues any new items for download.
    """
    sub = store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Fetch new items
    fetcher = get_fetcher(sub["subscription_type"])
    items = await fetcher.fetch_items(
        source_url=sub["source_url"],
        source_id=sub.get("source_id"),
        limit=sub.get("download_limit", 10) * 2,  # Fetch more than limit to find new ones
    )

    # Add new items to database
    new_items = []
    for item in items:
        existing = store.get_item_by_content_id(subscription_id, item.content_id)
        if not existing:
            item_id = str(uuid.uuid4())
            created = store.create_item(
                item_id=item_id,
                subscription_id=subscription_id,
                content_id=item.content_id,
                content_url=item.content_url,
                title=item.title,
                published_at=item.published_at,
            )
            if created:
                new_items.append(created)

    # Update last checked timestamp
    store.set_last_checked(subscription_id)

    if new_items:
        store.set_last_new_content(subscription_id)

    # Queue downloads in background
    items_queued = min(len(new_items), sub.get("download_limit", 10))

    if items_queued > 0:
        from ..core.subscription_worker import process_subscription_items
        background_tasks.add_task(
            process_subscription_items,
            subscription_id,
            limit=items_queued,
        )

    return CheckSubscriptionResponse(
        subscription_id=subscription_id,
        new_items_found=len(new_items),
        items_queued=items_queued,
        message=f"Found {len(new_items)} new items, queued {items_queued} for download",
    )


@router.get("/{subscription_id}/items", response_model=SubscriptionItemListResponse)
async def list_subscription_items(
    subscription_id: str,
    status: Optional[SubscriptionItemStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    store: SubscriptionStore = Depends(_get_store),
):
    """List items for a subscription."""
    sub = store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    store_status = StoreItemStatus(status.value) if status else None
    items = store.list_items(
        subscription_id=subscription_id,
        status=store_status,
        limit=limit,
        offset=offset,
    )

    total = store.count_items(subscription_id, store_status)

    return SubscriptionItemListResponse(
        items=[_item_to_response(item) for item in items],
        total=total,
        subscription_id=subscription_id,
    )


@router.post("/{subscription_id}/items/{item_id}/retry")
async def retry_item(
    subscription_id: str,
    item_id: str,
    background_tasks: BackgroundTasks,
    store: SubscriptionStore = Depends(_get_store),
):
    """Retry a failed subscription item."""
    sub = store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    item = store.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item["subscription_id"] != subscription_id:
        raise HTTPException(status_code=400, detail="Item does not belong to this subscription")

    if item["status"] not in [StoreItemStatus.FAILED.value, StoreItemStatus.SKIPPED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed or skipped items (current status: {item['status']})",
        )

    # Reset item status to pending
    store.set_item_status(item_id, StoreItemStatus.PENDING, error=None)

    # Queue for download
    from ..core.subscription_worker import process_single_item
    background_tasks.add_task(process_single_item, subscription_id, item_id)

    return {
        "status": "queued",
        "item_id": item_id,
        "message": "Item queued for retry",
    }


@router.delete("/{subscription_id}/items/{item_id}")
async def delete_item(
    subscription_id: str,
    item_id: str,
    store: SubscriptionStore = Depends(_get_store),
):
    """Delete a subscription item."""
    sub = store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    item = store.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item["subscription_id"] != subscription_id:
        raise HTTPException(status_code=400, detail="Item does not belong to this subscription")

    # Delete associated files
    from pathlib import Path

    for path_field in ["file_path", "transcription_path"]:
        if item.get(path_field):
            try:
                Path(item[path_field]).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete file {item[path_field]}: {e}")

    store.delete_item(item_id)

    return {"status": "deleted", "item_id": item_id}
