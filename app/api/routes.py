"""FastAPI routes for the AudioGrab API."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from ..core.downloader import DownloaderFactory
from ..core.converter import AudioConverter
from ..core.base import Platform as CorePlatform
from ..core.exceptions import ContentNotFoundError, UnsupportedPlatformError
from .schemas import (
    DownloadRequest,
    DownloadJob,
    JobStatus,
    ContentInfo,
    HealthResponse,
    Platform,
    TranscribeRequest,
    TranscriptionJob,
    TranscriptionSegment as TranscriptionSegmentSchema,
    TranscriptionOutputFormat,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job storage (use Redis/database for production)
jobs: Dict[str, DownloadJob] = {}
transcription_jobs: Dict[str, TranscriptionJob] = {}


def _core_platform_to_schema(platform: CorePlatform) -> Platform:
    """Convert core Platform enum to schema Platform enum."""
    mapping = {
        CorePlatform.X_SPACES: Platform.X_SPACES,
        CorePlatform.APPLE_PODCASTS: Platform.APPLE_PODCASTS,
        CorePlatform.SPOTIFY: Platform.SPOTIFY,
        CorePlatform.YOUTUBE: Platform.YOUTUBE,
        CorePlatform.XIAOYUZHOU: Platform.XIAOYUZHOU,
        CorePlatform.X_VIDEO: Platform.X_VIDEO,
        CorePlatform.YOUTUBE_VIDEO: Platform.YOUTUBE_VIDEO,
    }
    return mapping.get(platform, Platform.AUTO)


async def _process_download(job_id: str, request: DownloadRequest):
    """Background task to process a download."""
    job = jobs[job_id]
    job.status = JobStatus.PROCESSING
    job.progress = 0.1

    try:
        # Get appropriate downloader
        downloader = DownloaderFactory.get_downloader(request.url)
        job.platform = _core_platform_to_schema(downloader.platform)

        # Download
        result = await downloader.download(
            url=request.url,
            output_format=request.format.value,
            quality=request.quality.value,
        )

        if result.success and result.file_path:
            # Build content info from metadata
            if result.metadata:
                content_info = ContentInfo(
                    platform=_core_platform_to_schema(result.metadata.platform),
                    content_id=result.metadata.content_id,
                    title=result.metadata.title,
                    creator_name=result.metadata.creator_name,
                    creator_username=result.metadata.creator_username,
                    duration_seconds=int(result.metadata.duration_seconds) if result.metadata.duration_seconds else None,
                    show_name=result.metadata.show_name,
                    # Legacy fields for backward compatibility
                    host_username=result.metadata.creator_username,
                    host_display_name=result.metadata.creator_name,
                )
                job.content_info = content_info
                job.space_info = content_info  # Backward compatibility

            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            job.download_url = f"/api/download/{job_id}/file"
            job.file_size_mb = result.file_size_mb
            job.completed_at = datetime.utcnow()
            # Store file path for retrieval
            job._file_path = str(result.file_path)  # type: ignore
        else:
            job.status = JobStatus.FAILED
            job.error = str(result.error) if result.error else "Download failed"

    except ContentNotFoundError as e:
        job.status = JobStatus.FAILED
        job.error = f"Content not found: {e}"
    except UnsupportedPlatformError as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
    except Exception as e:
        logger.exception(f"Download error for job {job_id}")
        job.status = JobStatus.FAILED
        error_msg = str(e) if e else "Download failed"
        job.error = error_msg if error_msg else "Download failed"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    from ..core.platforms import (
        XSpacesDownloader,
        ApplePodcastsDownloader,
        SpotifyDownloader,
        YouTubeDownloader,
        XiaoyuzhouDownloader,
        XVideoDownloader,
        YouTubeVideoDownloader,
    )
    from ..core.transcriber import AudioTranscriber

    return HealthResponse(
        status="healthy",
        platforms={
            "x_spaces": XSpacesDownloader.is_available(),
            "apple_podcasts": ApplePodcastsDownloader.is_available(),
            "spotify": SpotifyDownloader.is_available(),
            "youtube": YouTubeDownloader.is_available(),
            "xiaoyuzhou": XiaoyuzhouDownloader.is_available(),
            "x_video": XVideoDownloader.is_available(),
            "youtube_video": YouTubeVideoDownloader.is_available(),
        },
        ffmpeg_available=AudioConverter.is_ffmpeg_available(),
        whisper_available=AudioTranscriber.is_available(),
        version="0.3.0",
    )


@router.post("/download", response_model=DownloadJob)
async def start_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a download job for audio content.

    Supports X Spaces, Apple Podcasts, and Spotify.
    Platform is auto-detected from URL if not specified.

    Returns a job ID that can be used to check status and retrieve the file.
    """
    logger.info(f"Download request: url={request.url}, platform={request.platform}, format={request.format}")

    # Validate URL and detect platform
    detected_platform = DownloaderFactory.detect_platform(request.url)

    if not detected_platform:
        raise HTTPException(
            status_code=400,
            detail="Unsupported URL. Supported platforms: X Spaces, Apple Podcasts, Spotify",
        )

    # Create job
    job_id = str(uuid.uuid4())
    job = DownloadJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        platform=_core_platform_to_schema(detected_platform),
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

    # Determine filename and media type
    path = Path(file_path)
    filename = path.name

    media_type_map = {
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".mp4": "video/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }
    media_type = media_type_map.get(path.suffix.lower(), "application/octet-stream")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
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


@router.get("/platforms")
async def get_platforms():
    """Get list of supported platforms and their availability."""
    from ..core.platforms import (
        XSpacesDownloader,
        ApplePodcastsDownloader,
        SpotifyDownloader,
        YouTubeDownloader,
        XiaoyuzhouDownloader,
        XVideoDownloader,
        YouTubeVideoDownloader,
    )

    return {
        "audio": [
            {
                "id": "x_spaces",
                "name": "X Spaces",
                "available": XSpacesDownloader.is_available(),
                "url_pattern": "x.com/i/spaces/...",
            },
            {
                "id": "apple_podcasts",
                "name": "Apple Podcasts",
                "available": ApplePodcastsDownloader.is_available(),
                "url_pattern": "podcasts.apple.com/...",
            },
            {
                "id": "spotify",
                "name": "Spotify",
                "available": SpotifyDownloader.is_available(),
                "url_pattern": "open.spotify.com/...",
            },
            {
                "id": "youtube",
                "name": "YouTube Audio",
                "available": YouTubeDownloader.is_available(),
                "url_pattern": "youtube.com/watch?v=...",
            },
            {
                "id": "xiaoyuzhou",
                "name": "小宇宙",
                "available": XiaoyuzhouDownloader.is_available(),
                "url_pattern": "xiaoyuzhoufm.com/episode/...",
            },
        ],
        "video": [
            {
                "id": "x_video",
                "name": "X/Twitter Video",
                "available": XVideoDownloader.is_available(),
                "url_pattern": "x.com/user/status/...",
            },
            {
                "id": "youtube_video",
                "name": "YouTube Video",
                "available": YouTubeVideoDownloader.is_available(),
                "url_pattern": "youtube.com/watch?v=...",
            },
        ],
    }


# ============ Transcription Endpoints ============


async def _process_transcription(job_id: str, request: TranscribeRequest, audio_path: Path):
    """Background task to process transcription."""
    from ..core.transcriber import AudioTranscriber

    job = transcription_jobs[job_id]
    job.status = JobStatus.PROCESSING
    job.progress = 0.1

    try:
        transcriber = AudioTranscriber(model_size=request.model.value)

        task = "translate" if request.translate else "transcribe"
        result = await transcriber.transcribe(
            audio_path=audio_path,
            language=request.language,
            task=task,
            vad_filter=True,
        )

        if result.success:
            job.text = result.text
            job.segments = [
                TranscriptionSegmentSchema(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                )
                for seg in (result.segments or [])
            ]
            job.language = result.language
            job.language_probability = result.language_probability
            job.duration_seconds = result.duration

            # Format output based on requested format
            if request.output_format == TranscriptionOutputFormat.SRT:
                job.formatted_output = transcriber.format_as_srt(result.segments or [])
            elif request.output_format == TranscriptionOutputFormat.VTT:
                job.formatted_output = transcriber.format_as_vtt(result.segments or [])
            elif request.output_format == TranscriptionOutputFormat.JSON:
                import json
                job.formatted_output = json.dumps({
                    "text": result.text,
                    "language": result.language,
                    "segments": [
                        {"start": s.start, "end": s.end, "text": s.text}
                        for s in (result.segments or [])
                    ]
                }, ensure_ascii=False, indent=2)
            else:
                job.formatted_output = result.text

            job.output_format = request.output_format
            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            job.completed_at = datetime.utcnow()
        else:
            job.status = JobStatus.FAILED
            job.error = result.error or "Transcription failed"

    except Exception as e:
        logger.exception(f"Transcription error for job {job_id}")
        job.status = JobStatus.FAILED
        job.error = str(e) if str(e) else "Transcription failed"


@router.post("/transcribe", response_model=TranscriptionJob)
async def start_transcription(
    request: TranscribeRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a transcription job.

    You can either:
    - Provide a URL to download and transcribe
    - Provide a job_id of a completed download to transcribe

    Supports the same platforms as download (X Spaces, YouTube, Podcasts, etc.)
    """
    from ..core.transcriber import AudioTranscriber

    # Validate request
    if not request.url and not request.job_id:
        raise HTTPException(
            status_code=400,
            detail="Either 'url' or 'job_id' must be provided",
        )

    audio_path = None
    source_url = request.url
    source_job_id = request.job_id

    # If job_id is provided, get the file from the completed download
    if request.job_id:
        if request.job_id not in jobs:
            raise HTTPException(status_code=404, detail="Download job not found")

        download_job = jobs[request.job_id]
        if download_job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Download job not completed (status: {download_job.status.value})",
            )

        file_path = getattr(download_job, "_file_path", None)
        if not file_path or not Path(file_path).exists():
            raise HTTPException(status_code=404, detail="Downloaded file not found")

        audio_path = Path(file_path)
        source_job_id = request.job_id

    # If URL is provided, we need to download first
    elif request.url:
        detected_platform = DownloaderFactory.detect_platform(request.url)
        if not detected_platform:
            raise HTTPException(
                status_code=400,
                detail="Unsupported URL for transcription",
            )

        # Download the audio first
        downloader = DownloaderFactory.get_downloader(request.url)
        result = await downloader.download(
            url=request.url,
            output_format="m4a",
            quality="high",
        )

        if not result.success or not result.file_path:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download audio: {result.error}",
            )

        audio_path = result.file_path
        source_url = request.url

    # Create transcription job
    job_id = str(uuid.uuid4())
    job = TranscriptionJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        progress=0.0,
        source_url=source_url,
        source_job_id=source_job_id,
        created_at=datetime.utcnow(),
    )
    transcription_jobs[job_id] = job

    # Start background transcription
    background_tasks.add_task(_process_transcription, job_id, request, audio_path)

    return job


@router.get("/transcribe/{job_id}", response_model=TranscriptionJob)
async def get_transcription_status(job_id: str):
    """Get the status of a transcription job."""
    if job_id not in transcription_jobs:
        raise HTTPException(status_code=404, detail="Transcription job not found")
    return transcription_jobs[job_id]


@router.delete("/transcribe/{job_id}")
async def cancel_transcription(job_id: str):
    """Cancel and remove a transcription job."""
    if job_id not in transcription_jobs:
        raise HTTPException(status_code=404, detail="Transcription job not found")

    del transcription_jobs[job_id]
    return {"status": "deleted", "job_id": job_id}
