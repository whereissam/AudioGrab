# AudioGrab

<p align="center">
  <img src="frontend/public/logo.svg" alt="AudioGrab" width="200">
</p>

Download audio and video from X Spaces, Apple Podcasts, Spotify, YouTube, and more.

## Features

- **Audio Downloads** - X Spaces, Apple Podcasts, Spotify, YouTube, 小宇宙
- **Video Downloads** - X/Twitter, YouTube (480p/720p/1080p)
- **Transcription** - Local Whisper (no API costs), 99+ languages, checkpoint resume
- **Speaker Diarization** - Identify different speakers (optional)
- **Smart Metadata** - Auto-embed ID3/MP4 tags with artwork
- **Job Recovery** - SQLite persistence, auto-resume on restart

## Quick Start

```bash
# Install
git clone https://github.com/yourusername/audiograb.git
cd audiograb
uv sync --extra transcribe

# Install system dependencies (macOS)
brew install ffmpeg yt-dlp

# Run
uv run audiograb-api          # Backend: http://localhost:8000
cd frontend && npm run dev    # Frontend: http://localhost:5173
```

## CLI Usage

```bash
uv run audiograb "https://x.com/i/spaces/1vOxwdyYrlqKB"
uv run audiograb "https://youtube.com/watch?v=xxx" -f mp3
uv run audiograb "https://podcasts.apple.com/..." -q highest
```

## API Quick Reference

| Endpoint | Description |
|----------|-------------|
| `POST /api/download` | Download audio/video |
| `POST /api/transcribe` | Transcribe from URL |
| `POST /api/transcribe/upload` | Upload & transcribe file |
| `GET /api/jobs` | List all jobs |
| `POST /api/jobs/{id}/retry` | Retry failed job |

Full API docs at http://localhost:8000/docs (Swagger UI)

## Supported Platforms

| Platform | URL Pattern |
|----------|-------------|
| X Spaces | `x.com/i/spaces/...` |
| Apple Podcasts | `podcasts.apple.com/...` |
| Spotify | `open.spotify.com/...` |
| YouTube | `youtube.com/watch?v=...` |
| 小宇宙 | `xiaoyuzhoufm.com/episode/...` |

## Configuration

Create `.env`:

```env
# Server
HOST=127.0.0.1            # Use 0.0.0.0 to expose to network
PORT=8000
DOWNLOAD_DIR=/tmp/audiograb

# API Authentication (optional)
# API_KEY=your-secret-key  # If set, requires X-API-Key header

# Optional
TELEGRAM_BOT_TOKEN=xxx
HUGGINGFACE_TOKEN=hf_xxx  # For speaker diarization
```

### API Authentication

By default, the API is open (no auth required) - suitable for local/self-hosted use.

To enable authentication, set `API_KEY` in `.env`:

```bash
# .env
API_KEY=my-secret-key

# Then include header in requests
curl -H "X-API-Key: my-secret-key" http://localhost:8000/api/health
```

## Documentation

- **API Docs**: http://localhost:8000/docs (Swagger UI)
- [Diarization Setup](docs/diarization-setup.md) - Speaker identification
- [X/Twitter API](docs/api-endpoints.md) - Internal API details

## License

MIT
