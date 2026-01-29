"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """Supported output formats."""

    M4A = "m4a"
    MP3 = "mp3"
    MP4 = "mp4"
    AAC = "aac"


class QualityPreset(str, Enum):
    """Quality presets for MP3 encoding."""

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
    """Request to download a Twitter Space."""

    url: str = Field(
        ...,
        description="Twitter Space URL",
        examples=["https://x.com/i/spaces/1vOxwdyYrlqKB"],
    )
    format: OutputFormat = Field(
        default=OutputFormat.M4A,
        description="Output audio format",
    )
    quality: QualityPreset = Field(
        default=QualityPreset.HIGH,
        description="Quality preset for MP3 encoding",
    )


class SpaceInfo(BaseModel):
    """Information about a Twitter Space."""

    space_id: str
    title: str
    host_username: str | None
    host_display_name: str | None
    state: str
    is_replay_available: bool
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    total_live_listeners: int
    total_replay_watched: int


class DownloadJob(BaseModel):
    """Download job status response."""

    job_id: str
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    space_info: SpaceInfo | None = None
    download_url: str | None = None
    file_size_mb: float | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class MetadataResponse(BaseModel):
    """Response for Space metadata lookup."""

    success: bool
    space: SpaceInfo | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    ffmpeg_available: bool
    auth_configured: bool
    version: str
