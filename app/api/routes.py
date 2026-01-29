"""FastAPI routes for the X Spaces Downloader API."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..core import SpaceDownloader, SpaceURLParser, SpaceNotFoundError
from .schemas import (
    DownloadRequest,
    DownloadJob,
    JobStatus,
    SpaceInfo,
    HealthResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job storage (use Redis/database for production)
jobs: Dict[str, DownloadJob] = {}


async def _process_download(job_id: str, request: DownloadRequest):
    """Background task to process a download."""
    job = jobs[job_id]
    job.status = JobStatus.PROCESSING
    job.progress = 0.1

    try:
        downloader = SpaceDownloader()

        # Download using yt-dlp
        result = await downloader.download(
            url=request.url,
            format=request.format.value,
            quality=request.quality.value,
        )

        if result.success and result.file_path:
            # Build space info from metadata
            if result.metadata:
                job.space_info = SpaceInfo(
                    space_id=result.metadata.space_id,
                    title=result.metadata.title,
                    host_username=result.metadata.host_username,
                    host_display_name=result.metadata.host_display_name,
                    state="Ended",
                    is_replay_available=True,
                    started_at=None,
                    ended_at=None,
                    duration_seconds=int(result.metadata.duration_seconds) if result.metadata.duration_seconds else None,
                    total_live_listeners=0,
                    total_replay_watched=0,
                )

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

    except SpaceNotFoundError as e:
        job.status = JobStatus.FAILED
        job.error = f"Space not found: {e}"
    except Exception as e:
        logger.exception(f"Download error for job {job_id}")
        job.status = JobStatus.FAILED
        job.error = str(e)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        ffmpeg_available=SpaceDownloader.is_yt_dlp_available(),
        auth_configured=True,  # Not needed for public Spaces
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
