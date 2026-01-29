"""FastAPI routes for the X Spaces Downloader API."""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..config import get_settings
from ..core import (
    AuthManager,
    SpaceDownloader,
    TwitterClient,
    SpaceURLParser,
    AuthenticationError,
    SpaceNotFoundError,
    SpaceNotAvailableError,
    XDownloaderError,
)
from ..core.merger import AudioMerger
from .schemas import (
    DownloadRequest,
    DownloadJob,
    JobStatus,
    SpaceInfo,
    MetadataResponse,
    HealthResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job storage (use Redis/database for production)
jobs: Dict[str, DownloadJob] = {}


def _metadata_to_space_info(metadata) -> SpaceInfo:
    """Convert SpaceMetadata to SpaceInfo schema."""
    return SpaceInfo(
        space_id=metadata.space_id,
        title=metadata.title,
        host_username=metadata.host_username,
        host_display_name=metadata.host_display_name,
        state=metadata.state,
        is_replay_available=metadata.is_replay_available,
        started_at=metadata.started_at,
        ended_at=metadata.ended_at,
        duration_seconds=metadata.duration_seconds,
        total_live_listeners=metadata.total_live_listeners,
        total_replay_watched=metadata.total_replay_watched,
    )


async def _process_download(job_id: str, request: DownloadRequest):
    """Background task to process a download."""
    job = jobs[job_id]
    job.status = JobStatus.PROCESSING
    job.progress = 0.1

    try:
        settings = get_settings()
        auth = AuthManager.from_env()
        downloader = SpaceDownloader(auth=auth)

        # Get metadata first
        async with TwitterClient(auth) as client:
            space_id = SpaceURLParser.extract_space_id(request.url)
            metadata = await client.get_space_metadata(space_id)
            job.space_info = _metadata_to_space_info(metadata)
            job.progress = 0.3

        # Download
        result = await downloader.download(
            url=request.url,
            format=request.format.value,
            quality=request.quality.value,
        )

        if result.success and result.file_path:
            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            job.download_url = f"/api/download/{job_id}/file"
            job.file_size_mb = result.file_size_mb
            job.completed_at = datetime.utcnow()
            # Store file path for retrieval
            job._file_path = str(result.file_path)  # type: ignore
        else:
            job.status = JobStatus.FAILED
            job.error = result.error or "Download failed"

    except AuthenticationError as e:
        job.status = JobStatus.FAILED
        job.error = f"Authentication error: {e}"
    except SpaceNotFoundError as e:
        job.status = JobStatus.FAILED
        job.error = f"Space not found: {e}"
    except SpaceNotAvailableError as e:
        job.status = JobStatus.FAILED
        job.error = f"Space not available: {e}"
    except Exception as e:
        logger.exception(f"Download error for job {job_id}")
        job.status = JobStatus.FAILED
        job.error = str(e)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        ffmpeg_available=AudioMerger.is_ffmpeg_available(),
        auth_configured=settings.has_auth,
        version="0.1.0",
    )


@router.post("/download", response_model=DownloadJob)
async def start_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a download job for a Twitter Space.

    Returns a job ID that can be used to check status and retrieve the file.
    """
    # Validate URL
    if not SpaceURLParser.is_valid_space_url(request.url):
        raise HTTPException(
            status_code=400,
            detail="Invalid Twitter Space URL",
        )

    # Check auth configuration
    settings = get_settings()
    if not settings.has_auth:
        raise HTTPException(
            status_code=500,
            detail="Server not configured with Twitter authentication",
        )

    # Create job
    job_id = str(uuid.uuid4())
    job = DownloadJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        progress=0.0,
        created_at=datetime.utcnow(),
    )
    jobs[job_id] = job

    # Start background download
    background_tasks.add_task(_process_download, job_id, request)

    return job


@router.get("/download/{job_id}", response_model=DownloadJob)
async def get_download_status(job_id: str):
    """Get the status of a download job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@router.get("/download/{job_id}/file")
async def get_download_file(job_id: str):
    """Download the completed file for a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed (status: {job.status.value})",
        )

    file_path = getattr(job, "_file_path", None)
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine filename for download
    path = Path(file_path)
    filename = path.name

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="audio/mp4" if path.suffix == ".m4a" else "audio/mpeg",
    )


@router.get("/space/{space_id}/metadata", response_model=MetadataResponse)
async def get_space_metadata(space_id: str):
    """Get metadata for a Twitter Space by ID."""
    settings = get_settings()
    if not settings.has_auth:
        raise HTTPException(
            status_code=500,
            detail="Server not configured with Twitter authentication",
        )

    try:
        auth = AuthManager.from_env()
        async with TwitterClient(auth) as client:
            metadata = await client.get_space_metadata(space_id)
            return MetadataResponse(
                success=True,
                space=_metadata_to_space_info(metadata),
            )
    except SpaceNotFoundError as e:
        return MetadataResponse(success=False, error=str(e))
    except SpaceNotAvailableError as e:
        return MetadataResponse(success=False, error=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.exception(f"Metadata fetch error for {space_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/download/{job_id}")
async def cancel_download(job_id: str):
    """Cancel and remove a download job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Clean up file if exists
    file_path = getattr(job, "_file_path", None)
    if file_path:
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass

    del jobs[job_id]
    return {"status": "deleted", "job_id": job_id}
