# AudioGrab

<p align="center">
  <img src="frontend/public/logo.svg" alt="AudioGrab" width="200">
</p>

Download audio from X Spaces, Apple Podcasts, Spotify, and YouTube.

## Features

- **X Spaces** - Download Twitter/X Spaces audio recordings
- **Apple Podcasts** - Download podcast episodes via RSS feeds
- **Spotify** - Download tracks and episodes via spotDL (YouTube matching)
- **YouTube** - Extract audio from YouTube videos
- **Format Conversion** - Convert between m4a, mp3, mp4, wav, flac, ogg
- **Web UI** - Modern React frontend with tabs for each platform
- **CLI Tool** - Simple command-line interface
- **REST API** - FastAPI backend for integrations
- **Telegram Bot** - Download via Telegram chat

## Requirements

- Python 3.10+
- FFmpeg (for audio conversion)
- yt-dlp (for X Spaces)
- spotDL (for Spotify, optional)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/audiograb.git
cd audiograb

# Install with uv
uv sync
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
│   │   ├── platforms/        # Platform-specific downloaders
│   │   │   ├── xspaces.py    # X Spaces (yt-dlp)
│   │   │   ├── apple_podcasts.py  # Apple Podcasts (RSS)
│   │   │   ├── spotify.py    # Spotify (spotDL)
│   │   │   └── youtube.py    # YouTube (yt-dlp)
│   │   └── exceptions.py
│   ├── api/                  # FastAPI REST API
│   ├── bot/                  # Telegram bot
│   ├── cli.py                # CLI interface
│   └── main.py               # API entry point
├── frontend/                 # React Web UI
│   ├── src/
│   │   ├── components/       # UI components
│   │   └── routes/           # Page routes
│   └── public/               # Static assets
├── docs/                     # Documentation
├── tests/
└── pyproject.toml
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/download` | Start download job |
| GET | `/api/download/{job_id}` | Get job status |
| GET | `/api/download/{job_id}/file` | Download completed file |
| DELETE | `/api/download/{job_id}` | Cancel job |
| GET | `/api/health` | Health check |
| GET | `/api/platforms` | List supported platforms |

## Supported Platforms

| Platform | URL Pattern | Tool Used |
|----------|-------------|-----------|
| X Spaces | `x.com/i/spaces/...` | yt-dlp |
| Apple Podcasts | `podcasts.apple.com/...` | HTTP + RSS |
| Spotify | `open.spotify.com/...` | spotDL |
| YouTube | `youtube.com/watch?v=...` | yt-dlp |

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
