# Architecture

## System Overview

The X Spaces Downloader consists of three main components:

1. **Core Library** (`xdownloader/core/`) - Handles all Twitter API interactions and audio processing
2. **FastAPI Backend** (`xdownloader/api/`) - REST API for external integrations
3. **Telegram Bot** (`xdownloader/bot/`) - User-friendly chat interface

## Download Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           DOWNLOAD FLOW                                   │
└──────────────────────────────────────────────────────────────────────────┘

User Input: https://x.com/i/spaces/1vOxwdyYrlqKB
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Extract Space ID                                                 │
│ ───────────────────────                                                 │
│ Input:  https://x.com/i/spaces/1vOxwdyYrlqKB                           │
│ Output: 1vOxwdyYrlqKB                                                   │
│ Method: Regex extraction                                                 │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Fetch Space Metadata                                            │
│ ──────────────────────────                                              │
│ Endpoint: GET /graphql/{hash}/AudioSpaceById?variables={id}             │
│ Output:   media_key = "28_2013482329990144000"                          │
│           state = "Ended"                                               │
│           is_replay_available = true                                    │
│           title, host, duration, etc.                                   │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Get Stream URL                                                   │
│ ─────────────────────                                                   │
│ Endpoint: GET /1.1/live_video_stream/status/{media_key}                 │
│ Output:   m3u8_url = "https://...pscp.tv/.../playlist.m3u8"            │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: Download & Merge Audio                                          │
│ ─────────────────────────────                                           │
│ Tool: FFmpeg                                                            │
│ Command: ffmpeg -i {m3u8_url} -c copy -vn output.m4a                   │
│ Or: Download segments concurrently, merge in memory                     │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  output.m4a │
                   │  (or .mp3)  │
                   └─────────────┘
```

## Module Structure

```
xdownloader/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry
│   ├── config.py            # Configuration management
│   │
│   ├── core/                # Core download functionality
│   │   ├── __init__.py
│   │   ├── auth.py          # Authentication handling
│   │   ├── client.py        # Twitter API client
│   │   ├── downloader.py    # Main download orchestration
│   │   ├── parser.py        # URL and response parsing
│   │   └── merger.py        # FFmpeg audio merging
│   │
│   ├── api/                 # FastAPI routes
│   │   ├── __init__.py
│   │   ├── routes.py        # API endpoints
│   │   ├── schemas.py       # Pydantic models
│   │   └── dependencies.py  # Dependency injection
│   │
│   └── bot/                 # Telegram bot
│       ├── __init__.py
│       ├── bot.py           # Bot initialization
│       └── handlers.py      # Message handlers
│
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_client.py
│   └── test_downloader.py
│
├── docs/                    # Documentation
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Core Components

### 1. Auth Module (`core/auth.py`)

Handles credential management:

```python
class AuthManager:
    """Manages Twitter authentication credentials."""

    def __init__(self, auth_token: str, ct0: str):
        self.auth_token = auth_token
        self.ct0 = ct0

    @classmethod
    def from_env(cls) -> "AuthManager":
        """Load credentials from environment variables."""
        pass

    @classmethod
    def from_cookie_file(cls, path: str) -> "AuthManager":
        """Load credentials from Netscape cookie file."""
        pass

    def get_headers(self) -> dict:
        """Build authenticated request headers."""
        pass
```

### 2. Twitter Client (`core/client.py`)

Handles all Twitter API interactions:

```python
class TwitterClient:
    """Async Twitter API client for Spaces."""

    async def get_space_metadata(self, space_id: str) -> SpaceMetadata:
        """Fetch AudioSpaceById GraphQL response."""
        pass

    async def get_stream_url(self, media_key: str) -> str:
        """Get m3u8 playlist URL from media key."""
        pass
```

### 3. Downloader (`core/downloader.py`)

Orchestrates the full download process:

```python
class SpaceDownloader:
    """Main downloader orchestration."""

    async def download(
        self,
        url: str,
        output_path: str = None,
        quality: str = "high",
        format: str = "m4a"
    ) -> DownloadResult:
        """Download a Space from URL to file."""
        pass
```

### 4. Merger (`core/merger.py`)

Handles audio processing with FFmpeg:

```python
class AudioMerger:
    """FFmpeg-based audio processing."""

    async def merge_hls_stream(
        self,
        m3u8_url: str,
        output_path: str,
        format: str = "m4a"
    ) -> None:
        """Download and merge HLS stream."""
        pass

    async def convert_to_mp3(
        self,
        input_path: str,
        output_path: str,
        bitrate: str = "192k"
    ) -> None:
        """Convert audio file to MP3."""
        pass
```

## API Design

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/download` | Start download job |
| GET | `/api/download/{job_id}` | Get download status |
| GET | `/api/download/{job_id}/file` | Download completed file |
| GET | `/api/space/{space_id}/metadata` | Get Space metadata |
| GET | `/health` | Health check |

### Request/Response Models

```python
# Request
class DownloadRequest(BaseModel):
    url: str                    # Space URL
    format: str = "m4a"         # Output format: m4a, mp3
    quality: str = "high"       # Quality: low, medium, high

# Response
class DownloadResponse(BaseModel):
    job_id: str
    status: str                 # pending, processing, completed, failed
    progress: float            # 0.0 - 1.0
    download_url: str | None   # Available when completed
    error: str | None          # Error message if failed
```

## Background Processing

For large files, use background task processing:

```python
from fastapi import BackgroundTasks

@app.post("/api/download")
async def start_download(
    request: DownloadRequest,
    background_tasks: BackgroundTasks
):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_download, job_id, request)
    return {"job_id": job_id, "status": "pending"}
```

## Telegram Bot Flow

```
User sends: https://x.com/i/spaces/1vOxwdyYrlqKB
                          │
                          ▼
              ┌─────────────────────┐
              │   Validate URL      │
              │   Extract Space ID  │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Reply: "Downloading │
              │  Space, please wait" │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Call Core Library  │
              │  SpaceDownloader    │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Upload audio file  │
              │  to Telegram chat   │
              └─────────────────────┘
```

## Error Handling

All modules use consistent error types:

```python
class XDownloaderError(Exception):
    """Base exception for all errors."""
    pass

class AuthenticationError(XDownloaderError):
    """Invalid or expired credentials."""
    pass

class SpaceNotFoundError(XDownloaderError):
    """Space ID not found or deleted."""
    pass

class SpaceNotAvailableError(XDownloaderError):
    """Space exists but replay not available."""
    pass

class DownloadError(XDownloaderError):
    """Failed to download audio stream."""
    pass

class FFmpegError(XDownloaderError):
    """FFmpeg processing failed."""
    pass
```

## Caching Strategy

To reduce API calls and improve performance:

1. **Metadata Cache**: Cache Space metadata for 1 hour
2. **Auth Token Validation**: Cache validation status for 5 minutes
3. **GraphQL Query Hash**: Cache discovered hashes, auto-refresh on 404

```python
from cachetools import TTLCache

metadata_cache = TTLCache(maxsize=1000, ttl=3600)  # 1 hour
auth_cache = TTLCache(maxsize=10, ttl=300)         # 5 minutes
```

## Configuration

Use Pydantic settings for configuration:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Authentication
    twitter_auth_token: str
    twitter_ct0: str

    # Or cookie file
    twitter_cookie_file: str | None = None

    # Telegram
    telegram_bot_token: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Downloads
    download_dir: str = "/tmp/xdownloader"
    max_concurrent_downloads: int = 5

    class Config:
        env_file = ".env"
```
