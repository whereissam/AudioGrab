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
│   │   ├── transcriber.py   # Whisper transcription
│   │   ├── job_store.py     # SQLite job persistence (+ batches, annotations)
│   │   ├── queue_manager.py # Priority-based download queue
│   │   ├── batch_manager.py # Batch download operations
│   │   ├── scheduler.py     # Scheduled downloads worker
│   │   ├── webhook_notifier.py    # Webhook delivery with retry
│   │   ├── websocket_manager.py   # Real-time annotation updates
│   │   ├── subscription_store.py   # SQLite subscription storage
│   │   ├── subscription_fetcher.py # RSS/YouTube fetchers
│   │   ├── subscription_worker.py  # Background subscription worker
│   │   ├── parser.py        # URL parsing
│   │   └── exceptions.py    # Custom exceptions
│   │
│   ├── api/                 # FastAPI routes
│   │   ├── __init__.py
│   │   ├── routes.py        # Download/transcribe endpoints
│   │   ├── batch_routes.py  # Batch download endpoints
│   │   ├── schedule_routes.py     # Scheduled download endpoints
│   │   ├── webhook_routes.py      # Webhook configuration
│   │   ├── annotation_routes.py   # Annotation CRUD + WebSocket
│   │   ├── subscription_routes.py # Subscription endpoints
│   │   └── schemas.py       # Pydantic models
│   │
│   └── bot/                 # Telegram bot
│       ├── __init__.py
│       └── bot.py           # Bot implementation
│
├── frontend/                # React frontend
│   └── src/
│       ├── components/
│       │   ├── downloader/  # Download components
│       │   │   └── BatchDownloadForm.tsx
│       │   ├── queue/       # Queue view
│       │   ├── schedule/    # Schedule modal
│       │   ├── settings/    # Webhook settings
│       │   ├── annotations/ # Annotation components
│       │   └── subscriptions/
│       └── routes/
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

#### Download & Transcribe

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/download` | Start download job |
| GET | `/api/download/{job_id}` | Get download status |
| GET | `/api/download/{job_id}/file` | Download completed file |
| PATCH | `/api/download/{job_id}/priority` | Update job priority |
| POST | `/api/transcribe` | Start transcription from URL |
| POST | `/api/transcribe/upload` | Upload file & transcribe |
| GET | `/api/transcribe/{job_id}` | Get transcription status |
| GET | `/api/add?url=...` | Quick add (browser extension) |
| GET | `/api/health` | Health check |

#### Queue & Batch

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/queue` | Get queue status |
| POST | `/api/batch/download` | Create batch from URL list |
| POST | `/api/batch/upload` | Create batch from file |
| GET | `/api/batch/{id}` | Get batch status |
| GET | `/api/batch/{id}/jobs` | List jobs in batch |
| DELETE | `/api/batch/{id}` | Cancel batch |

#### Scheduling

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/schedule/download` | Schedule a download |
| GET | `/api/schedule` | List scheduled downloads |
| DELETE | `/api/schedule/{id}` | Cancel scheduled download |
| PATCH | `/api/schedule/{id}` | Update schedule |

#### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/webhooks/config` | Get webhook config |
| POST | `/api/webhooks/test` | Test webhook URL |
| GET | `/api/webhooks/events` | List event types |

#### Annotations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/jobs/{id}/annotations` | Create annotation |
| GET | `/api/jobs/{id}/annotations` | List annotations |
| GET | `/api/annotations/{id}` | Get with replies |
| PUT | `/api/annotations/{id}` | Update annotation |
| DELETE | `/api/annotations/{id}` | Delete annotation |
| POST | `/api/annotations/{id}/reply` | Reply to annotation |
| WS | `/api/jobs/{id}/annotations/ws` | Real-time updates |

#### Subscriptions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/subscriptions` | Create subscription (RSS, YouTube channel/playlist) |
| GET | `/api/subscriptions` | List all subscriptions |
| GET | `/api/subscriptions/{id}` | Get subscription details |
| PATCH | `/api/subscriptions/{id}` | Update subscription |
| DELETE | `/api/subscriptions/{id}` | Delete subscription and items |
| POST | `/api/subscriptions/{id}/check` | Force check for new content |
| GET | `/api/subscriptions/{id}/items` | List subscription items |
| POST | `/api/subscriptions/{id}/items/{item_id}/retry` | Retry failed item |
| DELETE | `/api/subscriptions/{id}/items/{item_id}` | Delete item |

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

## Subscription System

The subscription system enables automatic downloading of new content from RSS feeds and YouTube.

### Subscription Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        SUBSCRIPTION FLOW                                  │
└──────────────────────────────────────────────────────────────────────────┘

User creates subscription (RSS/YouTube)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 1: Validate & Store                                                 │
│ ───────────────────────                                                 │
│ - Validate source URL (fetch feed/playlist)                            │
│ - Extract source name and ID                                           │
│ - Store in SQLite subscriptions table                                  │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 2: Background Worker (hourly)                                       │
│ ─────────────────────────────────                                       │
│ - Fetch items from source (RSS/yt-dlp --flat-playlist)                 │
│ - Compare with existing items (UNIQUE constraint)                       │
│ - Create new subscription_items with status='pending'                  │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 3: Download Items                                                   │
│ ─────────────────────                                                   │
│ - Direct HTTP download for RSS audio URLs                              │
│ - Platform downloader for YouTube URLs                                 │
│ - Optional format conversion                                           │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 4: Auto-Transcribe (optional)                                       │
│ ─────────────────────────────────                                       │
│ - If auto_transcribe=True, run Whisper                                 │
│ - Save transcript alongside audio file                                 │
└─────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Step 5: Cleanup                                                          │
│ ───────────────                                                         │
│ - If completed_count > download_limit                                  │
│ - Delete oldest completed items and files                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Subscription Types

| Type | Source | Fetcher |
|------|--------|---------|
| `rss` | RSS feed URL or Apple Podcasts URL | feedparser |
| `youtube_channel` | YouTube channel URL | yt-dlp --flat-playlist |
| `youtube_playlist` | YouTube playlist URL | yt-dlp --flat-playlist |

### Database Schema

```sql
-- Subscriptions table
CREATE TABLE subscriptions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    subscription_type TEXT NOT NULL,  -- 'rss', 'youtube_channel', 'youtube_playlist'
    source_url TEXT,
    source_id TEXT,
    platform TEXT NOT NULL,           -- 'podcast', 'youtube'
    enabled INTEGER DEFAULT 1,
    auto_transcribe INTEGER DEFAULT 0,
    transcribe_model TEXT DEFAULT 'base',
    download_limit INTEGER DEFAULT 10,
    output_format TEXT DEFAULT 'm4a',
    last_checked_at TEXT,
    total_downloaded INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Subscription items table
CREATE TABLE subscription_items (
    id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    content_url TEXT NOT NULL,
    title TEXT,
    published_at TEXT,
    status TEXT DEFAULT 'pending',    -- 'pending', 'downloading', 'completed', 'failed'
    file_path TEXT,
    transcription_path TEXT,
    error TEXT,
    discovered_at TEXT NOT NULL,
    downloaded_at TEXT,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE,
    UNIQUE(subscription_id, content_id)
);
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
