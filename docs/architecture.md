# Architecture

## System Overview

The X Spaces Downloader consists of these main components:

1. **Core Library** (`app/core/`) - Downloads Spaces via yt-dlp and converts audio formats
2. **FastAPI Backend** (`app/api/`) - REST API for external integrations
3. **Telegram Bot** (`app/bot/`) - User-friendly chat interface
4. **CLI** (`app/cli.py`) - Command-line interface

## Download Flow (using yt-dlp)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           DOWNLOAD FLOW                                   │
└──────────────────────────────────────────────────────────────────────────┘

User Input: https://x.com/i/spaces/1vOxwdyYrlqKB
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Validate URL & Extract Space ID                                  │
│ ───────────────────────────────────────                                 │
│ Input:  https://x.com/i/spaces/1vOxwdyYrlqKB                           │
│ Output: 1vOxwdyYrlqKB                                                   │
│ Method: Regex extraction via SpaceURLParser                             │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: yt-dlp handles everything                                        │
│ ─────────────────────────────────                                       │
│ - Gets guest token from Twitter API                                     │
│ - Fetches GraphQL metadata (AudioSpaceById)                             │
│ - Gets m3u8 stream URL (live_video_stream/status)                      │
│ - Downloads HLS segments via FFmpeg                                     │
│ - Merges into single audio file                                         │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Optional Format Conversion                                       │
│ ─────────────────────────────────                                       │
│ Tool: FFmpeg via AudioConverter                                         │
│ Formats: mp3, mp4, aac, wav, ogg, flac                                 │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  output.m4a │
                   │  (or .mp3)  │
                   └─────────────┘
```

## Why yt-dlp?

Twitter's internal GraphQL API changes frequently (endpoint hashes, required variables).
yt-dlp maintains these changes and handles:
- Guest token generation
- GraphQL schema updates
- Rate limiting
- Error recovery

## Module Structure

```
xdownloader/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry
│   ├── cli.py               # CLI interface
│   ├── config.py            # Configuration management
│   │
│   ├── core/                # Core functionality
│   │   ├── __init__.py
│   │   ├── downloader.py    # yt-dlp based downloader
│   │   ├── converter.py     # FFmpeg audio converter
│   │   ├── parser.py        # URL parsing
│   │   └── exceptions.py    # Custom exceptions
│   │
│   ├── api/                 # FastAPI routes
│   │   ├── __init__.py
│   │   ├── routes.py        # API endpoints
│   │   └── schemas.py       # Pydantic models
│   │
│   └── bot/                 # Telegram bot
│       ├── __init__.py
│       └── bot.py           # Bot implementation
│
├── tests/
│   └── test_parser.py
│
├── docs/                    # Documentation
├── pyproject.toml
└── README.md
```

## Core Components

### 1. SpaceDownloader (`core/downloader.py`)

Downloads Twitter Spaces using yt-dlp:

```python
class SpaceDownloader:
    """Downloads Twitter Spaces using yt-dlp."""

    async def download(
        self,
        url: str,
        output_path: str | None = None,
        format: str = "m4a",
        quality: str = "high",
    ) -> DownloadResult:
        """Download a Space from URL to file."""
        pass

    async def get_metadata(self, url: str) -> SpaceMetadata | None:
        """Get metadata without downloading."""
        pass
```

### 2. AudioConverter (`core/converter.py`)

Converts audio between formats using FFmpeg:

```python
class AudioConverter:
    """FFmpeg-based audio format converter."""

    async def convert(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        output_format: str = "mp3",
        quality: str = "high",
        keep_original: bool = True,
    ) -> Path:
        """Convert audio file to another format."""
        pass

    # Convenience methods
    async def to_mp3(self, input_path, quality="high") -> Path: ...
    async def to_mp4(self, input_path, quality="high") -> Path: ...
    async def to_wav(self, input_path) -> Path: ...
    async def to_flac(self, input_path) -> Path: ...
```

**Supported formats:** mp3, mp4, aac, wav, ogg, flac

**Quality presets:** low (64k), medium (128k), high (192k), highest (320k)

### 3. SpaceURLParser (`core/parser.py`)

URL validation and parsing:

```python
class SpaceURLParser:
    @classmethod
    def extract_space_id(cls, url: str) -> str:
        """Extract Space ID from URL."""
        pass

    @classmethod
    def is_valid_space_url(cls, url: str) -> bool:
        """Check if URL is a valid Twitter Space URL."""
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
