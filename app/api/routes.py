"""FastAPI routes for the AudioGrab API."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
import aiofiles

from .auth import verify_api_key

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
    FetchTranscriptRequest,
)

logger = logging.getLogger(__name__)

# Apply optional API key auth to all routes
# If API_KEY env var is set, all requests require X-API-Key header
# If API_KEY is not set, API is open (for self-hosted use)
router = APIRouter(dependencies=[Depends(verify_api_key)])

# In-memory job storage (use Redis/database for production)
jobs: Dict[str, DownloadJob] = {}
# Import shared transcription jobs storage
from .transcription_store import transcription_jobs


def _core_platform_to_schema(platform: CorePlatform) -> Platform:
    """Convert core Platform enum to schema Platform enum."""
    mapping = {
        CorePlatform.X_SPACES: Platform.X_SPACES,
        CorePlatform.APPLE_PODCASTS: Platform.APPLE_PODCASTS,
        CorePlatform.SPOTIFY: Platform.SPOTIFY,
        CorePlatform.YOUTUBE: Platform.YOUTUBE,
        CorePlatform.XIAOYUZHOU: Platform.XIAOYUZHOU,
        CorePlatform.DISCORD: Platform.DISCORD,
        CorePlatform.X_VIDEO: Platform.X_VIDEO,
        CorePlatform.YOUTUBE_VIDEO: Platform.YOUTUBE_VIDEO,
        CorePlatform.INSTAGRAM: Platform.INSTAGRAM,
        CorePlatform.XIAOHONGSHU: Platform.XIAOHONGSHU,
    }
    return mapping.get(platform, Platform.AUTO)


async def _process_download(job_id: str, request: DownloadRequest):
    """Background task to process a download."""
    import shutil

    job = jobs[job_id]
    job.status = JobStatus.PROCESSING
    job.progress = 0.1

    try:
        # Get appropriate downloader based on platform selection
        if request.platform != Platform.AUTO:
            # User explicitly selected a platform (e.g., YOUTUBE_VIDEO for video)
            from ..core.base import Platform as CorePlatform
            core_platform = CorePlatform(request.platform.value)
            downloader = DownloaderFactory.get_downloader_for_platform(core_platform)
        else:
            # Auto-detect from URL
            downloader = DownloaderFactory.get_downloader(request.url)
        job.platform = _core_platform_to_schema(downloader.platform)

        # Download
        result = await downloader.download(
            url=request.url,
            output_format=request.format.value,
            quality=request.quality.value,
        )

        if result.success and result.file_path:
            final_path = result.file_path

            # Move to custom output directory if specified
            output_dir = getattr(request, 'output_dir', None)
            if output_dir:
                try:
                    output_path = Path(output_dir)
                    output_path.mkdir(parents=True, exist_ok=True)
                    new_path = output_path / result.file_path.name
                    shutil.move(str(result.file_path), str(new_path))
                    final_path = new_path
                    logger.info(f"[{job_id}] Moved file to {new_path}")
                except Exception as e:
                    logger.error(f"[{job_id}] Failed to move file: {e}")

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
            job.file_path = str(final_path)  # Show where file was saved
            job.file_size_mb = result.file_size_mb
            job.completed_at = datetime.utcnow()
            # Store internal attributes
            job._file_path = str(final_path)  # type: ignore
            job._keep_file = getattr(request, 'keep_file', True)  # type: ignore
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
    """Health check endpoint (liveness probe)."""
    from ..core.platforms import (
        XSpacesDownloader,
        ApplePodcastsDownloader,
        SpotifyDownloader,
        YouTubeDownloader,
        XiaoyuzhouDownloader,
        DiscordAudioDownloader,
        XVideoDownloader,
        YouTubeVideoDownloader,
        InstagramVideoDownloader,
        XiaohongshuVideoDownloader,
    )
    from ..core.transcriber import AudioTranscriber
    from ..core.diarizer import SpeakerDiarizer
    from ..core.summarizer import TranscriptSummarizer
    from ..core.enhancer import AudioEnhancer

    return HealthResponse(
        status="healthy",
        platforms={
            "x_spaces": XSpacesDownloader.is_available(),
            "apple_podcasts": ApplePodcastsDownloader.is_available(),
            "spotify": SpotifyDownloader.is_available(),
            "youtube": YouTubeDownloader.is_available(),
            "xiaoyuzhou": XiaoyuzhouDownloader.is_available(),
            "discord": DiscordAudioDownloader.is_available(),
            "x_video": XVideoDownloader.is_available(),
            "youtube_video": YouTubeVideoDownloader.is_available(),
            "instagram": InstagramVideoDownloader.is_available(),
            "xiaohongshu": XiaohongshuVideoDownloader.is_available(),
        },
        ffmpeg_available=AudioConverter.is_ffmpeg_available(),
        whisper_available=AudioTranscriber.is_available(),
        diarization_available=SpeakerDiarizer.is_available(),
        summarization_available=TranscriptSummarizer.is_available(),
        enhancement_available=AudioEnhancer.is_available(),
        version="0.3.0",
    )


@router.get("/readyz")
async def readiness_check():
    """
    Readiness probe - checks if the service is ready to accept traffic.

    Verifies:
    - Database connection is working
    - Download directory is writable
    """
    from ..core.job_store import get_job_store
    from ..config import get_settings
    from pathlib import Path

    errors = []

    # Check database connection
    try:
        job_store = get_job_store()
        # Try a simple query
        job_store.get_jobs_by_status()
    except Exception as e:
        errors.append(f"Database: {str(e)}")

    # Check download directory is writable
    try:
        settings = get_settings()
        download_dir = Path(settings.download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)
        test_file = download_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        errors.append(f"Download directory: {str(e)}")

    if errors:
        raise HTTPException(
            status_code=503,
            detail={"status": "not ready", "errors": errors},
        )

    return {"status": "ready"}


@router.get("/add")
async def quick_add(
    url: str,
    action: str = "transcribe",
    background_tasks: BackgroundTasks = None,
):
    """
    Quick add endpoint for browser extension and bookmarklet.

    Accepts a URL and action (transcribe or download) via query parameters.
    Starts the appropriate job and returns the job ID.

    Example: /api/add?url=https://youtube.com/watch?v=abc&action=transcribe
    """
    from fastapi import BackgroundTasks as BT

    if background_tasks is None:
        background_tasks = BT()

    # Detect platform from URL
    detected_platform = DownloaderFactory.detect_platform(url)

    if not detected_platform:
        raise HTTPException(
            status_code=400,
            detail="Unsupported URL. Supported: X Spaces, YouTube, Apple Podcasts, Spotify, Discord, 小宇宙",
        )

    job_id = str(uuid.uuid4())

    if action == "download":
        # Create download job
        job = DownloadJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            platform=_core_platform_to_schema(detected_platform),
            progress=0.0,
            created_at=datetime.utcnow(),
        )
        jobs[job_id] = job

        # Create download request
        request = DownloadRequest(url=url)
        background_tasks.add_task(_process_download, job_id, request)

        return {
            "job_id": job_id,
            "action": "download",
            "status": "pending",
            "message": f"Download started for {detected_platform.value}",
        }
    else:
        # Create transcription job (default action)
        job = TranscriptionJob(
            job_id=job_id,
            status=JobStatus.PENDING,
            progress=0.0,
            source_url=url,
            created_at=datetime.utcnow(),
        )
        transcription_jobs[job_id] = job

        # Create transcribe request with defaults
        from .schemas import WhisperModelSize

        class QuickTranscribeRequest:
            def __init__(self):
                self.url = url
                self.model = WhisperModelSize.BASE
                self.output_format = TranscriptionOutputFormat.TEXT
                self.language = None
                self.translate = False
                self.diarize = False
                self.num_speakers = None

        request = QuickTranscribeRequest()
        background_tasks.add_task(_process_transcription, job_id, request, None)

        return {
            "job_id": job_id,
            "action": "transcribe",
            "status": "pending",
            "message": f"Transcription started for {detected_platform.value}",
        }


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
            detail="Unsupported URL. Supported platforms: X Spaces, Apple Podcasts, Spotify, Discord",
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


@router.patch("/download/{job_id}/priority")
async def update_download_priority(job_id: str, priority: int):
    """
    Update the priority of a pending download job.

    Priority levels: 1 (lowest) to 10 (highest).
    Only affects jobs that are still in the queue.
    """
    from .schemas import PriorityUpdate
    from ..core.queue_manager import get_queue_manager
    from ..core.job_store import get_job_store

    if priority < 1 or priority > 10:
        raise HTTPException(
            status_code=400,
            detail="Priority must be between 1 and 10",
        )

    # Update in queue
    queue_manager = get_queue_manager()
    updated = await queue_manager.update_priority(job_id, priority)

    if not updated:
        # Job might not be in queue, try updating in database directly
        job_store = get_job_store()
        job = job_store.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job_store.update_priority(job_id, priority)

    return {
        "job_id": job_id,
        "priority": priority,
        "status": "updated",
    }


@router.get("/queue")
async def get_queue_status():
    """Get the current download queue status."""
    from ..core.queue_manager import get_queue_manager

    queue_manager = get_queue_manager()
    return queue_manager.get_queue_status()


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
        DiscordAudioDownloader,
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
            {
                "id": "discord",
                "name": "Discord Audio",
                "available": DiscordAudioDownloader.is_available(),
                "url_pattern": "cdn.discordapp.com/attachments/...",
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
    """Background task to process transcription with checkpoint and diarization support."""
    from ..core.transcriber import AudioTranscriber, TranscriptionSegment

    job = transcription_jobs[job_id]
    job.status = JobStatus.PROCESSING
    job.progress = 0.1

    enhanced_path = None  # Track enhanced file for cleanup/keeping
    original_audio_path = audio_path  # Track original for cleanup

    try:
        # Apply audio enhancement if requested
        enhance = getattr(request, 'enhance', False)
        if enhance:
            from ..core.enhancer import AudioEnhancer, EnhancementPreset as CoreEnhancementPreset

            enhancer = AudioEnhancer()
            preset_value = getattr(request, 'enhancement_preset', 'medium')
            if hasattr(preset_value, 'value'):
                preset_value = preset_value.value
            preset = CoreEnhancementPreset(preset_value)

            logger.info(f"[{job_id}] Applying {preset.value} audio enhancement...")
            result = await enhancer.enhance(audio_path, preset, keep_original=True)

            if result.success and result.enhanced_path:
                logger.info(f"[{job_id}] Audio enhancement complete: {result.enhanced_path}")
                enhanced_path = result.enhanced_path
                audio_path = result.enhanced_path
            else:
                logger.warning(f"[{job_id}] Audio enhancement failed: {result.error}, continuing with original audio")

        transcriber = AudioTranscriber(model_size=request.model.value)

        task = "translate" if request.translate else "transcribe"
        result = await transcriber.transcribe(
            audio_path=audio_path,
            language=request.language,
            task=task,
            vad_filter=True,
            job_id=job_id,  # Enable checkpointing
            output_format=request.output_format.value,
        )

        if result.success:
            segments = result.segments or []

            # Run diarization if requested
            diarize = getattr(request, 'diarize', False)
            num_speakers = getattr(request, 'num_speakers', None)

            if diarize:
                try:
                    from ..core.diarizer import SpeakerDiarizer

                    if SpeakerDiarizer.is_available():
                        logger.info(f"[{job_id}] Running speaker diarization...")
                        diarizer = SpeakerDiarizer()
                        speaker_segments = await diarizer.diarize(
                            audio_path,
                            num_speakers=num_speakers,
                        )

                        # Assign speakers to transcription segments
                        diarized = diarizer.assign_speakers_to_segments(
                            segments, speaker_segments
                        )

                        # Convert back to TranscriptionSegment with speaker labels
                        segments = [
                            TranscriptionSegment(
                                start=d.start,
                                end=d.end,
                                text=d.text,
                                speaker=d.speaker,
                            )
                            for d in diarized
                        ]
                        logger.info(f"[{job_id}] Diarization complete")
                    else:
                        logger.warning(
                            f"[{job_id}] Diarization requested but pyannote not available"
                        )
                except Exception as e:
                    logger.error(f"[{job_id}] Diarization failed: {e}")
                    # Continue without diarization

            job.text = result.text
            job.segments = [
                TranscriptionSegmentSchema(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    speaker=seg.speaker,
                )
                for seg in segments
            ]
            job.language = result.language
            job.language_probability = result.language_probability
            job.duration_seconds = result.duration

            # Format output based on requested format
            has_speakers = diarize and any(s.speaker for s in segments)

            if request.output_format == TranscriptionOutputFormat.SRT:
                if has_speakers:
                    job.formatted_output = transcriber.format_as_srt_with_speakers(segments)
                else:
                    job.formatted_output = transcriber.format_as_srt(segments)
            elif request.output_format == TranscriptionOutputFormat.VTT:
                job.formatted_output = transcriber.format_as_vtt(segments)
            elif request.output_format == TranscriptionOutputFormat.JSON:
                import json
                job.formatted_output = json.dumps({
                    "text": result.text,
                    "language": result.language,
                    "segments": [
                        {
                            "start": s.start,
                            "end": s.end,
                            "text": s.text,
                            "speaker": s.speaker,
                        }
                        for s in segments
                    ],
                    "diarized": has_speakers,
                }, ensure_ascii=False, indent=2)
            elif request.output_format == TranscriptionOutputFormat.DIALOGUE:
                job.formatted_output = transcriber.format_as_dialogue(segments)
            else:
                job.formatted_output = result.text

            job.output_format = request.output_format

            # Save transcription to file if save_to is specified
            save_to = getattr(request, 'save_to', None)
            if save_to and job.formatted_output:
                try:
                    output_path = Path(save_to)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(job.formatted_output, encoding='utf-8')
                    job.output_file = str(output_path)
                    logger.info(f"[{job_id}] Saved transcription to {output_path}")
                except Exception as e:
                    logger.error(f"[{job_id}] Failed to save transcription: {e}")

            # Handle enhanced audio file based on keep_enhanced
            keep_enhanced = getattr(request, 'keep_enhanced', False)
            if enhanced_path and enhanced_path.exists():
                if keep_enhanced:
                    job.enhanced_file = str(enhanced_path)
                    logger.info(f"[{job_id}] Keeping enhanced audio: {enhanced_path}")
                else:
                    try:
                        enhanced_path.unlink()
                        logger.info(f"[{job_id}] Deleted enhanced audio file")
                    except Exception as e:
                        logger.warning(f"[{job_id}] Failed to delete enhanced audio: {e}")

            # Handle original audio file based on keep_audio
            keep_audio = getattr(request, 'keep_audio', False)
            if keep_audio:
                job.audio_file = str(original_audio_path)
            else:
                # Delete temp original audio file
                try:
                    if original_audio_path.exists():
                        original_audio_path.unlink()
                        logger.info(f"[{job_id}] Deleted temp audio file")
                except Exception as e:
                    logger.warning(f"[{job_id}] Failed to delete temp audio: {e}")

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


@router.get("/transcribe/resumable")
async def list_resumable_transcriptions():
    """List all transcription jobs that can be resumed."""
    from ..core.transcriber import AudioTranscriber

    transcriber = AudioTranscriber()
    jobs = transcriber.get_resumable_jobs()
    return {"resumable_jobs": jobs}


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


@router.post("/transcribe/{job_id}/resume", response_model=TranscriptionJob)
async def resume_transcription(
    job_id: str,
    background_tasks: BackgroundTasks,
):
    """Resume a previously interrupted transcription job."""
    from ..core.transcriber import AudioTranscriber
    from ..core.checkpoint import CheckpointManager

    checkpoint_manager = CheckpointManager()
    checkpoint = checkpoint_manager.load(job_id)

    if not checkpoint:
        raise HTTPException(
            status_code=404,
            detail=f"No checkpoint found for job {job_id}",
        )

    audio_path = Path(checkpoint.audio_path)
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio file no longer exists: {checkpoint.audio_path}",
        )

    # Create or update job in memory
    job = TranscriptionJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        progress=checkpoint.last_end_time / checkpoint.total_duration if checkpoint.total_duration else 0,
        source_url=f"resume://{audio_path.name}",
        created_at=datetime.fromisoformat(checkpoint.created_at),
    )
    transcription_jobs[job_id] = job

    # Create mock request from checkpoint
    class ResumeTranscribeRequest:
        def __init__(self):
            self.model = type("Model", (), {"value": checkpoint.model_size})()
            self.output_format = type("Format", (), {"value": checkpoint.output_format})()
            self.language = checkpoint.language
            self.translate = checkpoint.task == "translate"

    request = ResumeTranscribeRequest()

    # Start background transcription (will resume from checkpoint)
    background_tasks.add_task(_process_transcription, job_id, request, audio_path)

    return job


# ============ Transcript Fetch Endpoints ============


def _format_srt(segments: list[dict]) -> str:
    """Format segments as SRT subtitle format."""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]
        start_h, start_r = divmod(start, 3600)
        start_m, start_s = divmod(start_r, 60)
        end_h, end_r = divmod(end, 3600)
        end_m, end_s = divmod(end_r, 60)
        lines.append(str(i))
        lines.append(
            f"{int(start_h):02d}:{int(start_m):02d}:{start_s:06.3f}".replace(".", ",")
            + " --> "
            + f"{int(end_h):02d}:{int(end_m):02d}:{end_s:06.3f}".replace(".", ",")
        )
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _format_vtt(segments: list[dict]) -> str:
    """Format segments as WebVTT subtitle format."""
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]
        start_h, start_r = divmod(start, 3600)
        start_m, start_s = divmod(start_r, 60)
        end_h, end_r = divmod(end, 3600)
        end_m, end_s = divmod(end_r, 60)
        lines.append(
            f"{int(start_h):02d}:{int(start_m):02d}:{start_s:06.3f}"
            + " --> "
            + f"{int(end_h):02d}:{int(end_m):02d}:{end_s:06.3f}"
        )
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


@router.get("/transcript/check")
async def check_transcript_availability(url: str):
    """
    Check if a transcript can be fetched for the given URL.

    Returns availability status, platform, and available languages (YouTube).
    """
    from ..core.transcript_fetcher import TranscriptFetcher

    fetcher = TranscriptFetcher()

    if not fetcher.can_fetch_transcript(url):
        return {"available": False, "platform": None, "languages": []}

    # Determine platform
    import re
    if re.search(r"(youtube\.com|youtu\.be)", url):
        platform = "youtube"
    elif re.search(r"open\.spotify\.com/episode/", url):
        platform = "spotify"
    else:
        platform = None

    # List available languages (YouTube only)
    languages = []
    if platform == "youtube":
        try:
            languages = await fetcher.list_available_languages(url)
        except Exception:
            pass

    available = platform == "spotify" or len(languages) > 0

    return {
        "available": available,
        "platform": platform,
        "languages": languages,
    }


@router.post("/transcript/fetch", response_model=TranscriptionJob)
async def fetch_transcript(request: FetchTranscriptRequest):
    """
    Fetch an existing transcript from YouTube or Spotify.

    Returns a completed TranscriptionJob immediately (no background task needed).
    The result is stored in the same transcription_jobs dict as Whisper results,
    so all downstream features (summarize, translate, sentiment, export) work unchanged.
    """
    import json
    from ..core.transcript_fetcher import TranscriptFetcher

    fetcher = TranscriptFetcher()

    if not fetcher.can_fetch_transcript(request.url):
        raise HTTPException(
            status_code=400,
            detail="URL does not support transcript fetching. Use Whisper transcription instead.",
        )

    result = await fetcher.fetch_transcript(request.url, request.language)

    if not result.success:
        raise HTTPException(status_code=422, detail=result.error or "Failed to fetch transcript")

    # Build segments
    segments = [
        TranscriptionSegmentSchema(start=s["start"], end=s["end"], text=s["text"])
        for s in result.segments
    ]

    # Format output
    if request.output_format == TranscriptionOutputFormat.SRT:
        formatted = _format_srt(result.segments)
    elif request.output_format == TranscriptionOutputFormat.VTT:
        formatted = _format_vtt(result.segments)
    elif request.output_format == TranscriptionOutputFormat.JSON:
        formatted = json.dumps(
            {
                "text": result.text,
                "language": result.language,
                "source": result.source,
                "segments": result.segments,
            },
            ensure_ascii=False,
            indent=2,
        )
    else:
        formatted = result.text

    # Create a completed transcription job
    job_id = str(uuid.uuid4())
    job = TranscriptionJob(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        progress=1.0,
        text=result.text,
        segments=segments,
        language=result.language or None,
        duration_seconds=result.duration_seconds,
        formatted_output=formatted,
        output_format=request.output_format,
        source_url=request.url,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    transcription_jobs[job_id] = job

    return job


# ============ Job Management Endpoints ============


@router.get("/jobs")
async def list_all_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
):
    """List all jobs with optional filtering."""
    from ..core.job_store import get_job_store, JobStatus as StoreJobStatus, JobType

    job_store = get_job_store()

    if status:
        try:
            status_enum = StoreJobStatus(status)
            jobs = job_store.get_jobs_by_status(status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    else:
        # Get all jobs (recent first)
        with job_store._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            jobs = [job_store._row_to_dict(row) for row in rows]

    if job_type:
        jobs = [j for j in jobs if j["job_type"] == job_type]

    return {"jobs": jobs[:limit], "total": len(jobs)}


@router.get("/jobs/resumable")
async def list_resumable_jobs():
    """List all jobs that can be resumed (failed or interrupted)."""
    from ..core.job_store import get_job_store

    job_store = get_job_store()
    jobs = job_store.get_resumable_jobs()

    return {
        "resumable_jobs": jobs,
        "total": len(jobs),
    }


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
):
    """Retry a failed or interrupted job from its last successful phase."""
    from ..core.job_store import get_job_store
    from ..core.workflow import WorkflowProcessor

    job_store = get_job_store()
    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "completed":
        raise HTTPException(status_code=400, detail="Job already completed")

    # Run retry in background
    async def _retry():
        processor = WorkflowProcessor(job_store)
        await processor.retry_job(job_id)

    background_tasks.add_task(_retry)

    return {
        "status": "retrying",
        "job_id": job_id,
        "previous_status": job["status"],
    }


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files."""
    from ..core.job_store import get_job_store

    job_store = get_job_store()
    job = job_store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete associated files
    for path_field in ["raw_file_path", "converted_file_path"]:
        if job.get(path_field):
            path = Path(job[path_field])
            if path.exists():
                path.unlink()

    # Delete from database
    job_store.delete_job(job_id)

    return {"status": "deleted", "job_id": job_id}


@router.post("/cleanup")
async def cleanup_storage(
    max_age_hours: int = 24,
    delete_all: bool = False,
):
    """
    Clean up old checkpoints and completed jobs.

    - max_age_hours: Delete checkpoints/jobs older than this (default: 24)
    - delete_all: If true, delete ALL checkpoints (use with caution)
    """
    from ..core.job_store import get_job_store
    from ..core.checkpoint import CheckpointManager

    job_store = get_job_store()
    checkpoint_manager = CheckpointManager()

    results = {
        "checkpoints_deleted": 0,
        "jobs_deleted": 0,
    }

    # Clean up checkpoints
    if delete_all:
        results["checkpoints_deleted"] = checkpoint_manager.cleanup_all()
    else:
        results["checkpoints_deleted"] = checkpoint_manager.cleanup_old_checkpoints(max_age_hours)

    # Clean up old completed/failed jobs
    results["jobs_deleted"] = job_store.cleanup_old_jobs(days=max_age_hours // 24 or 1)

    return results


@router.post("/backup")
async def create_backup():
    """Create a backup of the jobs database."""
    from ..core.job_store import get_job_store

    job_store = get_job_store()
    backup_path = job_store.backup()

    return {
        "status": "success",
        "backup_path": str(backup_path),
        "message": "Database backup created",
    }


@router.get("/backups")
async def list_backups():
    """List available database backups."""
    from ..core.job_store import get_job_store

    job_store = get_job_store()
    backups = job_store.list_backups()

    return {
        "backups": backups,
        "total": len(backups),
    }


@router.get("/storage")
async def get_storage_info():
    """Get storage usage information."""
    from ..core.job_store import get_job_store
    from ..core.checkpoint import CheckpointManager
    from ..config import get_settings
    import shutil

    settings = get_settings()
    job_store = get_job_store()
    checkpoint_manager = CheckpointManager()

    download_dir = Path(settings.download_dir)

    # Calculate download directory size
    download_size = 0
    file_count = 0
    if download_dir.exists():
        for f in download_dir.rglob("*"):
            if f.is_file():
                download_size += f.stat().st_size
                file_count += 1

    # Get disk usage
    disk = shutil.disk_usage(download_dir.parent if download_dir.exists() else "/tmp")

    return {
        "download_dir": str(download_dir),
        "download_size_mb": round(download_size / (1024 * 1024), 2),
        "file_count": file_count,
        "checkpoints": checkpoint_manager.get_storage_info(),
        "jobs_in_db": len(job_store.get_jobs_by_status()),
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
    }


@router.post("/transcribe/upload", response_model=TranscriptionJob)
async def transcribe_uploaded_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    model: str = Form(default="base"),
    output_format: str = Form(default="text"),
    language: str = Form(default=None),
    diarize: str = Form(default="false"),
    num_speakers: str = Form(default=None),
    enhance: str = Form(default="false"),
    enhancement_preset: str = Form(default="medium"),
    keep_enhanced: str = Form(default="false"),
):
    """
    Transcribe an uploaded audio file.

    Supports: mp3, m4a, wav, mp4, webm, ogg, flac
    """
    from ..core.transcriber import AudioTranscriber
    from ..config import get_settings

    settings = get_settings()

    # Validate file extension
    allowed_extensions = {".mp3", ".m4a", ".wav", ".mp4", ".webm", ".ogg", ".flac", ".aac"}
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    # Save uploaded file
    upload_dir = Path(settings.download_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}{file_ext}"

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Create transcription job
    job_id = str(uuid.uuid4())

    # Map form values to schema enums
    from .schemas import TranscriptionOutputFormat, WhisperModelSize

    try:
        output_format_enum = TranscriptionOutputFormat(output_format)
    except ValueError:
        output_format_enum = TranscriptionOutputFormat.TEXT

    job = TranscriptionJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        progress=0.0,
        source_url=f"upload://{file.filename}",
        created_at=datetime.utcnow(),
    )
    transcription_jobs[job_id] = job

    # Create a mock request object for the background task
    class UploadTranscribeRequest:
        def __init__(self):
            self.model = WhisperModelSize(model) if model in [e.value for e in WhisperModelSize] else WhisperModelSize.BASE
            self.output_format = output_format_enum
            self.language = language if language else None
            self.translate = False
            self.diarize = diarize.lower() == "true"
            self.num_speakers = int(num_speakers) if num_speakers and num_speakers.isdigit() else None
            self.enhance = enhance.lower() == "true"
            self.enhancement_preset = enhancement_preset
            self.keep_enhanced = keep_enhanced.lower() == "true"

    request = UploadTranscribeRequest()

    # Start background transcription
    background_tasks.add_task(_process_transcription, job_id, request, file_path)

    return job


# ============ Summarization Endpoints ============


@router.post("/summarize")
async def summarize_text(request: dict):
    """
    Summarize text using an LLM.

    Supports multiple summary types:
    - bullet_points: Main ideas as bullet points
    - chapters: Chapter markers with timestamps (for transcripts)
    - key_topics: Major themes and topics
    - action_items: Tasks and follow-ups (for meetings)
    - full: Comprehensive summary with all elements
    """
    from ..core.summarizer import TranscriptSummarizer, SummaryType as CoreSummaryType

    text = request.get("text", "")
    summary_type_str = request.get("summary_type", "bullet_points")

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        summary_type = CoreSummaryType(summary_type_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid summary type. Valid types: {[t.value for t in CoreSummaryType]}",
        )

    summarizer = TranscriptSummarizer.from_settings()

    if not summarizer.provider:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Set LLM_PROVIDER and required API keys in .env",
        )

    if not summarizer.provider.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider '{summarizer.provider.name}' is not available",
        )

    try:
        result = await summarizer.summarize(text, summary_type)
        return {
            "summary_type": result.summary_type.value,
            "content": result.content,
            "model": result.model,
            "provider": result.provider,
            "tokens_used": result.tokens_used,
        }
    except Exception as e:
        logger.exception("Summarization failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize/job/{job_id}")
async def summarize_job(job_id: str, summary_type: str = "bullet_points"):
    """
    Summarize a completed transcription job.

    Takes the job_id of a completed transcription and generates a summary.
    """
    from ..core.summarizer import TranscriptSummarizer, SummaryType as CoreSummaryType

    # Find the transcription job
    job = transcription_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcription job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status.value}",
        )

    if not job.text:
        raise HTTPException(status_code=400, detail="Job has no transcription text")

    try:
        summary_type_enum = CoreSummaryType(summary_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid summary type. Valid types: {[t.value for t in CoreSummaryType]}",
        )

    summarizer = TranscriptSummarizer.from_settings()

    if not summarizer.provider:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Set LLM_PROVIDER and required API keys in .env",
        )

    if not summarizer.provider.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider '{summarizer.provider.name}' is not available",
        )

    try:
        result = await summarizer.summarize(job.text, summary_type_enum)
        return {
            "job_id": job_id,
            "summary_type": result.summary_type.value,
            "content": result.content,
            "model": result.model,
            "provider": result.provider,
            "tokens_used": result.tokens_used,
        }
    except Exception as e:
        logger.exception("Summarization failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summarize/providers")
async def list_summarization_providers():
    """
    List available LLM providers and their status.
    """
    from ..config import get_settings
    from ..core.summarizer import OllamaProvider, OpenAIProvider, AnthropicProvider

    settings = get_settings()

    providers = []

    # Check Ollama
    ollama = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
    providers.append({
        "name": "ollama",
        "available": ollama.is_available(),
        "model": settings.ollama_model,
        "configured": True,
        "is_default": settings.llm_provider == "ollama",
    })

    # Check OpenAI
    providers.append({
        "name": "openai",
        "available": bool(settings.openai_api_key),
        "model": settings.openai_model,
        "configured": bool(settings.openai_api_key),
        "is_default": settings.llm_provider == "openai",
    })

    # Check OpenAI-compatible
    providers.append({
        "name": "openai_compatible",
        "available": bool(settings.openai_api_key and settings.openai_base_url),
        "model": settings.openai_model,
        "base_url": settings.openai_base_url,
        "configured": bool(settings.openai_api_key and settings.openai_base_url),
        "is_default": settings.llm_provider == "openai_compatible",
    })

    # Check Anthropic
    providers.append({
        "name": "anthropic",
        "available": bool(settings.anthropic_api_key),
        "model": settings.anthropic_model,
        "configured": bool(settings.anthropic_api_key),
        "is_default": settings.llm_provider == "anthropic",
    })

    return {
        "default_provider": settings.llm_provider,
        "providers": providers,
    }
