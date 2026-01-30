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
    embed_metadata: bool = Field(
        default=True,
        description="Embed ID3/MP4 metadata tags (title, artist, artwork) into audio file",
    )
    output_dir: Optional[str] = Field(
        default=None,
        description="Custom output directory for the downloaded file. If not specified, uses default temp directory.",
    )
    keep_file: bool = Field(
        default=True,
        description="Keep the downloaded file after completion. Set to False for temp downloads.",
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
    file_path: Optional[str] = Field(
        default=None,
        description="Local file path where the download was saved",
    )
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
    diarization_available: bool = False
    summarization_available: bool = False
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
    DIALOGUE = "dialogue"  # Speaker-attributed dialogue format


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
    diarize: bool = Field(
        default=False,
        description="Enable speaker diarization (identify different speakers)",
    )
    num_speakers: Optional[int] = Field(
        default=None,
        description="Exact number of speakers (if known, improves diarization accuracy)",
    )
    save_to: Optional[str] = Field(
        default=None,
        description="Path to save transcription output file. If not specified, results are only returned via API.",
    )
    keep_audio: bool = Field(
        default=False,
        description="Keep the downloaded audio file after transcription. Default is False (temp download).",
    )


class TranscriptionSegment(BaseModel):
    """A segment of transcribed text with timestamps."""

    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Transcribed text")
    speaker: Optional[str] = Field(
        default=None,
        description="Speaker label (e.g., 'SPEAKER_00') if diarization was enabled",
    )


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
    # Output file paths
    output_file: Optional[str] = Field(
        default=None,
        description="Path where transcription output was saved (if save_to was specified)",
    )
    audio_file: Optional[str] = Field(
        default=None,
        description="Path to audio file (if keep_audio was True)",
    )


# ============ Summarization Schemas ============


class SummaryType(str, Enum):
    """Types of summaries that can be generated."""

    BULLET_POINTS = "bullet_points"
    CHAPTERS = "chapters"
    KEY_TOPICS = "key_topics"
    ACTION_ITEMS = "action_items"
    FULL = "full"


class LLMProvider(str, Enum):
    """Available LLM providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"


class SummarizeRequest(BaseModel):
    """Request to summarize text."""

    text: str = Field(
        ...,
        description="Text to summarize (typically a transcript)",
    )
    summary_type: SummaryType = Field(
        default=SummaryType.BULLET_POINTS,
        description="Type of summary to generate",
    )
    provider: Optional[LLMProvider] = Field(
        default=None,
        description="LLM provider to use. If not specified, uses configured default.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model to use. If not specified, uses configured default for the provider.",
    )


class SummarizeFromJobRequest(BaseModel):
    """Request to summarize a completed transcription job."""

    job_id: str = Field(
        ...,
        description="Job ID of a completed transcription to summarize",
    )
    summary_type: SummaryType = Field(
        default=SummaryType.BULLET_POINTS,
        description="Type of summary to generate",
    )


class SummaryResponse(BaseModel):
    """Response containing a generated summary."""

    summary_type: SummaryType
    content: str = Field(description="The generated summary")
    model: str = Field(description="Model used for generation")
    provider: str = Field(description="Provider used for generation")
    tokens_used: Optional[int] = Field(
        default=None,
        description="Number of tokens used for generation",
    )
