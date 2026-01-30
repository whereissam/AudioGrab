# AudioGrab

<p align="center">
  <img src="frontend/public/logo.svg" alt="AudioGrab" width="200">
</p>

Download audio and video from X Spaces, Apple Podcasts, Spotify, YouTube, and more.

## Features

### Audio Downloads
- **X Spaces** - Download Twitter/X Spaces audio recordings
- **Apple Podcasts** - Download podcast episodes via RSS feeds
- **Spotify** - Download tracks and episodes via spotDL (YouTube matching)
- **YouTube** - Extract audio from YouTube videos
- **小宇宙 (Xiaoyuzhou)** - Download Chinese podcast episodes

### Video Downloads
- **X/Twitter** - Download videos from tweets
- **YouTube** - Download YouTube videos (480p/720p/1080p)

### Transcription (Speech-to-Text)
- **Local Whisper** - Transcribe audio using faster-whisper (runs locally, no API costs)
- **Multiple Models** - tiny, base, small, medium, large-v3, turbo
- **Output Formats** - Plain text, SRT subtitles, VTT subtitles, JSON with timestamps
- **Auto Language Detection** - Supports 99+ languages
- **Resume Support** - Checkpoint-based resume for long audio files

### Reliability Features
- **Job Persistence** - SQLite-based storage survives server restarts
- **Two-Phase Downloads** - Download first, then convert (keeps original until done)
- **Auto Recovery** - Resumes interrupted jobs on server startup
- **Retry Endpoint** - Manually retry failed jobs from last successful phase

### Interfaces
- **Web UI** - Modern React frontend with tabs for Audio/Video/Transcribe
- **CLI Tool** - Simple command-line interface
- **REST API** - FastAPI backend for integrations
- **Telegram Bot** - Download via Telegram chat

## Requirements

- Python 3.10+
- FFmpeg (for audio conversion)
- yt-dlp (for X Spaces, YouTube)
- spotDL (for Spotify, optional)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/audiograb.git
cd audiograb

# Install with uv
uv sync

# Install with transcription support
uv sync --extra transcribe
```

### Install Dependencies

```bash
# macOS
brew install ffmpeg yt-dlp

# Install spotDL for Spotify support (optional)
uv add spotdl
```

## Usage

### Run Web UI

```bash
# Start backend
uv run audiograb-api
# API available at http://localhost:8000

# Start frontend (in another terminal)
cd frontend
bun install
bun run dev
# Frontend available at http://localhost:5173
```

### CLI Usage

```bash
# Download X Space
uv run audiograb "https://x.com/i/spaces/1vOxwdyYrlqKB"

# Download Apple Podcast episode
uv run audiograb "https://podcasts.apple.com/us/podcast/show/id123456789"

# Download Spotify track/episode
uv run audiograb "https://open.spotify.com/episode/abc123"

# Download YouTube audio
uv run audiograb "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Specify format
uv run audiograb "https://x.com/i/spaces/1vOxwdyYrlqKB" -f mp3

# Specify quality
uv run audiograb "https://x.com/i/spaces/1vOxwdyYrlqKB" -q highest
```

**Supported formats:** mp3, m4a, mp4, aac, wav, ogg, flac

**Quality presets:** low (64k), medium (128k), high (192k), highest (320k)

### Transcription

The Web UI has a **Transcribe** tab for audio-to-text transcription.

**Via API:**

```bash
# Transcribe from URL
curl -X POST http://localhost:8000/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=xxx", "model": "base", "output_format": "srt"}'

# Upload and transcribe local file
curl -X POST http://localhost:8000/api/transcribe/upload \
  -F "file=@audio.mp3" \
  -F "model=base" \
  -F "output_format=text"

# Check transcription status
curl http://localhost:8000/api/transcribe/{job_id}

# List resumable transcription jobs
curl http://localhost:8000/api/transcribe/resumable

# Resume interrupted transcription
curl -X POST http://localhost:8000/api/transcribe/{job_id}/resume
```

**Whisper Models:**

| Model | Size | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | 39M | Fastest | Good |
| base | 74M | Fast | Better |
| small | 244M | Medium | Good |
| medium | 769M | Slow | High |
| large-v3 | 1.5B | Slowest | Best |
| turbo | 809M | Fast | High |

### Run Telegram Bot

```bash
# Set TELEGRAM_BOT_TOKEN in .env first
uv run audiograb-bot
```

## Project Structure

```
audiograb/
├── app/
│   ├── core/
│   │   ├── base.py           # Abstract base classes
│   │   ├── downloader.py     # Factory pattern downloader
│   │   ├── converter.py      # FFmpeg audio converter
│   │   ├── transcriber.py    # Whisper transcription
│   │   ├── checkpoint.py     # Transcription checkpoints
│   │   ├── job_store.py      # SQLite job persistence
│   │   ├── workflow.py       # Two-phase download workflow
│   │   ├── platforms/        # Platform-specific downloaders
│   │   │   ├── xspaces.py    # X Spaces (yt-dlp)
│   │   │   ├── apple_podcasts.py  # Apple Podcasts (RSS)
│   │   │   ├── spotify.py    # Spotify (spotDL)
│   │   │   ├── youtube.py    # YouTube (yt-dlp)
│   │   │   └── xiaoyuzhou.py # 小宇宙 podcasts
│   │   └── exceptions.py
│   ├── api/                  # FastAPI REST API
│   ├── bot/                  # Telegram bot
│   ├── cli.py                # CLI interface
│   └── main.py               # API entry point
├── frontend/                 # React Web UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── downloader/   # Download/transcribe components
│   │   │   └── ui/           # UI primitives
│   │   └── routes/           # Page routes
│   └── public/               # Static assets
├── docs/                     # Documentation
├── tests/
└── pyproject.toml
```

## API Endpoints

### Downloads

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/download` | Start download job |
| GET | `/api/download/{job_id}` | Get job status |
| GET | `/api/download/{job_id}/file` | Download completed file |
| DELETE | `/api/download/{job_id}` | Cancel job |

### Transcription

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/transcribe` | Transcribe from URL |
| POST | `/api/transcribe/upload` | Upload and transcribe file |
| GET | `/api/transcribe/{job_id}` | Get transcription status |
| GET | `/api/transcribe/resumable` | List resumable jobs |
| POST | `/api/transcribe/{job_id}/resume` | Resume interrupted job |

### Job Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/resumable` | List jobs that can be retried |
| POST | `/api/jobs/{job_id}/retry` | Retry failed job |
| DELETE | `/api/jobs/{job_id}` | Delete job and files |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/platforms` | List supported platforms |
| GET | `/api/storage` | Storage usage info |
| POST | `/api/cleanup` | Clean up old checkpoints/jobs |

## Supported Platforms

| Platform | URL Pattern | Tool Used |
|----------|-------------|-----------|
| X Spaces | `x.com/i/spaces/...` | yt-dlp |
| Apple Podcasts | `podcasts.apple.com/...` | HTTP + RSS |
| Spotify | `open.spotify.com/...` | spotDL |
| YouTube | `youtube.com/watch?v=...` | yt-dlp |

## Reliability & Recovery

AudioGrab is designed to handle long downloads and transcriptions reliably:

### Two-Phase Downloads
1. **Download Phase** - Raw file downloaded (yt-dlp handles resume)
2. **Convert Phase** - Convert to target format (keeps original until done)

If the server crashes during conversion, the raw file is preserved and conversion can be retried.

### Transcription Checkpoints
- Progress saved every 5 segments
- On crash/restart, transcription resumes from last checkpoint
- Checkpoint deleted on successful completion
- **Auto-cleanup**: Checkpoints older than 24 hours deleted on server shutdown

### Job Persistence
- All jobs stored in SQLite (`/tmp/audiograb/jobs.db`)
- Server startup automatically recovers unfinished jobs
- Old completed jobs cleaned up after 7 days

### Manual Recovery
```bash
# List jobs that can be retried
curl http://localhost:8000/api/jobs/resumable

# Retry a specific job
curl -X POST http://localhost:8000/api/jobs/{job_id}/retry
```

### Storage Management
```bash
# Check storage usage
curl http://localhost:8000/api/storage

# Clean up old checkpoints (older than 24 hours)
curl -X POST "http://localhost:8000/api/cleanup?max_age_hours=24"

# Delete ALL checkpoints (use with caution)
curl -X POST "http://localhost:8000/api/cleanup?delete_all=true"
```

## Configuration

Create a `.env` file:

```env
# Optional: Telegram bot
TELEGRAM_BOT_TOKEN=your_bot_token

# Server settings
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Downloads
DOWNLOAD_DIR=/tmp/audiograb
```

## License

MIT
