"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Supported platforms."""

    X_SPACES = "x_spaces"
    APPLE_PODCASTS = "apple_podcasts"
    SPOTIFY = "spotify"
    YOUTUBE = "youtube"
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
    version: str
