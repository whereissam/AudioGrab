"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Supported platforms."""

    # Audio
    X_SPACES = "x_spaces"
    APPLE_PODCASTS = "apple_podcasts"
    SPOTIFY = "spotify"
    YOUTUBE = "youtube"
    XIAOYUZHOU = "xiaoyuzhou"
    # Video
    X_VIDEO = "x_video"
    YOUTUBE_VIDEO = "youtube_video"
    AUTO = "auto"  # Auto-detect from URL


class OutputFormat(str, Enum):
    """Supported output formats."""

    M4A = "m4a"
    MP3 = "mp3"
    MP4 = "mp4"
    AAC = "aac"


class QualityPreset(str, Enum):
    """Quality presets for encoding."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    HIGHEST = "highest"


class JobStatus(str, Enum):
    """Download job statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DownloadRequest(BaseModel):
    """Request to download audio."""

    url: str = Field(
        ...,
        description="Audio content URL",
        examples=[
            "https://x.com/i/spaces/1vOxwdyYrlqKB",
            "https://podcasts.apple.com/us/podcast/show/id123456789",
            "https://open.spotify.com/episode/abc123",
        ],
    )
    platform: Platform = Field(
        default=Platform.AUTO,
        description="Platform (auto-detected if not specified)",
    )
    format: OutputFormat = Field(
        default=OutputFormat.M4A,
        description="Output audio format",
    )
    quality: QualityPreset = Field(
        default=QualityPreset.HIGH,
        description="Quality preset for encoding",
    )


class ContentInfo(BaseModel):
    """Information about downloaded content."""

    platform: Platform
    content_id: str
    title: str
    creator_name: Optional[str] = None
    creator_username: Optional[str] = None
    duration_seconds: Optional[int] = None
    # Podcast-specific
    show_name: Optional[str] = None
    episode_number: Optional[int] = None
    # Legacy X Spaces fields (for backward compatibility)
    host_username: Optional[str] = None
    host_display_name: Optional[str] = None


# Backward compatibility alias
SpaceInfo = ContentInfo


class DownloadJob(BaseModel):
    """Download job status response."""

    job_id: str
    status: JobStatus
    platform: Optional[Platform] = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    content_info: Optional[ContentInfo] = None
    # Legacy field for backward compatibility
    space_info: Optional[ContentInfo] = None
    download_url: Optional[str] = None
    file_size_mb: Optional[float] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class MetadataResponse(BaseModel):
    """Response for content metadata lookup."""

    success: bool
    platform: Optional[Platform] = None
    content: Optional[ContentInfo] = None
    # Legacy field
    space: Optional[ContentInfo] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    platforms: dict[str, bool] = Field(
        default_factory=dict,
        description="Availability of each platform's dependencies",
    )
    ffmpeg_available: bool
    whisper_available: bool = False
    version: str


# ============ Transcription Schemas ============


class WhisperModelSize(str, Enum):
    """Available Whisper model sizes."""

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE_V2 = "large-v2"
    LARGE_V3 = "large-v3"
    TURBO = "turbo"


class TranscriptionOutputFormat(str, Enum):
    """Output format for transcription."""

    TEXT = "text"
    SRT = "srt"
    VTT = "vtt"
    JSON = "json"


class TranscribeRequest(BaseModel):
    """Request to transcribe audio."""

    url: Optional[str] = Field(
        default=None,
        description="URL to download and transcribe (X Spaces, YouTube, Podcast, etc.)",
    )
    job_id: Optional[str] = Field(
        default=None,
        description="Job ID of a completed download to transcribe",
    )
    language: Optional[str] = Field(
        default=None,
        description="Language code (e.g., 'en', 'zh', 'ja'). Auto-detect if not specified.",
    )
    model: WhisperModelSize = Field(
        default=WhisperModelSize.BASE,
        description="Whisper model size (larger = more accurate but slower)",
    )
    output_format: TranscriptionOutputFormat = Field(
        default=TranscriptionOutputFormat.TEXT,
        description="Output format for transcription",
    )
    translate: bool = Field(
        default=False,
        description="Translate to English (if source is non-English)",
    )


class TranscriptionSegment(BaseModel):
    """A segment of transcribed text with timestamps."""

    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Transcribed text")


class TranscriptionJob(BaseModel):
    """Transcription job status response."""

    job_id: str
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    # Transcription results
    text: Optional[str] = None
    segments: Optional[list[TranscriptionSegment]] = None
    language: Optional[str] = None
    language_probability: Optional[float] = None
    duration_seconds: Optional[float] = None
    # Formatted output
    formatted_output: Optional[str] = None
    output_format: Optional[TranscriptionOutputFormat] = None
    # Metadata
    source_url: Optional[str] = None
    source_job_id: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
