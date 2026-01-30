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
    # Priority & Scheduling
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Priority level (1=low, 5=normal, 10=high)",
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="Schedule download for a specific time (ISO format)",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for job completion notification",
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
    enhancement_available: bool = False
    version: str


# ============ Enhancement Schemas ============


class EnhancementPreset(str, Enum):
    """Audio enhancement presets."""

    NONE = "none"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


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
    enhance: bool = Field(
        default=False,
        description="Apply audio enhancement (noise reduction, voice isolation) before transcription",
    )
    enhancement_preset: EnhancementPreset = Field(
        default=EnhancementPreset.MEDIUM,
        description="Audio enhancement preset: none, light, medium, or heavy",
    )
    keep_enhanced: bool = Field(
        default=False,
        description="Keep the enhanced audio file after transcription (only applies if enhance=True)",
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
    enhanced_file: Optional[str] = Field(
        default=None,
        description="Path to enhanced audio file (if enhance=True and keep_enhanced=True)",
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


# ============ Priority Queue Schemas ============


class PriorityUpdate(BaseModel):
    """Request to update job priority."""

    priority: int = Field(
        ...,
        ge=1,
        le=10,
        description="New priority level (1=low, 10=high)",
    )


class QueueStatus(BaseModel):
    """Current queue status."""

    pending: int = Field(description="Number of jobs waiting in queue")
    processing: int = Field(description="Number of jobs currently processing")
    max_concurrent: int = Field(description="Maximum concurrent jobs")
    processing_jobs: list[str] = Field(description="IDs of jobs being processed")
    jobs: list[dict] = Field(description="Jobs in queue with priority info")


# ============ Batch Schemas ============


class BatchDownloadRequest(BaseModel):
    """Request to create a batch download."""

    urls: list[str] = Field(
        ...,
        min_length=1,
        description="List of URLs to download",
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional name for the batch",
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Priority level for all jobs in batch",
    )
    format: OutputFormat = Field(
        default=OutputFormat.M4A,
        description="Output format for all downloads",
    )
    quality: QualityPreset = Field(
        default=QualityPreset.HIGH,
        description="Quality preset for all downloads",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for batch completion notification",
    )


class BatchResponse(BaseModel):
    """Response for batch creation."""

    batch_id: str
    name: Optional[str]
    total_jobs: int
    job_ids: list[str]
    status: str
    created_at: datetime


class BatchStatus(BaseModel):
    """Batch status response."""

    batch_id: str
    name: Optional[str]
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    status: str
    webhook_url: Optional[str]
    created_at: datetime
    updated_at: datetime


# ============ Schedule Schemas ============


class ScheduleDownloadRequest(BaseModel):
    """Request to schedule a download."""

    url: str = Field(
        ...,
        description="URL to download",
    )
    scheduled_at: datetime = Field(
        ...,
        description="When to start the download (ISO format)",
    )
    platform: Platform = Field(
        default=Platform.AUTO,
        description="Platform (auto-detected if not specified)",
    )
    format: OutputFormat = Field(
        default=OutputFormat.M4A,
        description="Output format",
    )
    quality: QualityPreset = Field(
        default=QualityPreset.HIGH,
        description="Quality preset",
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Priority level when scheduled time arrives",
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for completion notification",
    )


class ScheduledJob(BaseModel):
    """Scheduled job response."""

    job_id: str
    url: str
    scheduled_at: datetime
    priority: int
    status: str
    created_at: datetime


# ============ Webhook Schemas ============


class WebhookConfig(BaseModel):
    """Webhook configuration."""

    default_url: Optional[str] = Field(
        default=None,
        description="Default webhook URL for all jobs",
    )
    retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for failed webhooks",
    )
    retry_delay: int = Field(
        default=60,
        description="Delay between retries in seconds",
    )


class WebhookTestRequest(BaseModel):
    """Request to test a webhook."""

    url: str = Field(
        ...,
        description="Webhook URL to test",
    )


class WebhookTestResponse(BaseModel):
    """Response from webhook test."""

    success: bool
    error: Optional[str] = None


# ============ Annotation Schemas ============


class CreateAnnotationRequest(BaseModel):
    """Request to create an annotation."""

    content: str = Field(
        ...,
        min_length=1,
        description="Annotation content",
    )
    user_id: str = Field(
        ...,
        description="ID of the user creating the annotation",
    )
    user_name: Optional[str] = Field(
        default=None,
        description="Display name of the user",
    )
    segment_start: Optional[float] = Field(
        default=None,
        ge=0,
        description="Start time of the transcript segment (seconds)",
    )
    segment_end: Optional[float] = Field(
        default=None,
        ge=0,
        description="End time of the transcript segment (seconds)",
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="ID of parent annotation if this is a reply",
    )


class UpdateAnnotationRequest(BaseModel):
    """Request to update an annotation."""

    content: str = Field(
        ...,
        min_length=1,
        description="Updated annotation content",
    )


class AnnotationResponse(BaseModel):
    """Annotation response."""

    id: str
    job_id: str
    content: str
    user_id: str
    user_name: Optional[str] = None
    segment_start: Optional[float] = None
    segment_end: Optional[float] = None
    parent_id: Optional[str] = None
    replies: list["AnnotationResponse"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# Fix forward reference for nested annotations
AnnotationResponse.model_rebuild()
