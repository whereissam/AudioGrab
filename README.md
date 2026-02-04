# AudioGrab

<p align="center">
  <img src="frontend/public/logo.svg" alt="AudioGrab" width="200">
</p>

Download audio and video from X Spaces, Apple Podcasts, Spotify, YouTube, Instagram, 小红书, and more.

## Features

- **Audio Downloads** - X Spaces, Apple Podcasts, Spotify, YouTube, 小宇宙
- **Video Downloads** - X/Twitter, YouTube, Instagram, 小红书 (480p/720p/1080p)
- **Transcription** - Local Whisper or API models (OpenAI, Groq, etc.), 99+ languages
- **Live Transcription** - Real-time microphone transcription via WebSocket
- **Translation** - TranslateGemma (local) or AI providers, 55+ languages
- **Sentiment Analysis** - Emotional heatmap timeline, detect heated moments & vibe shifts
- **Audio Enhancement** - Noise reduction & voice isolation (FFmpeg-based)
- **Speaker Diarization** - Identify different speakers (optional)
- **Smart Metadata** - Auto-embed ID3/MP4 tags with artwork
- **Job Recovery** - SQLite persistence, auto-resume on restart
- **Batch Downloads** - Download multiple URLs at once with progress tracking
- **Priority Queue** - Prioritize important downloads (1-10 levels)
- **Scheduled Downloads** - Schedule downloads for specific times
- **Webhook Notifications** - Get notified when jobs complete/fail
- **Collaborative Annotations** - Add comments to transcripts with real-time sync

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

## API

Full API documentation available at http://localhost:8000/docs (Swagger UI)

## Supported Platforms

### Audio
| Platform | URL Pattern |
|----------|-------------|
| X Spaces | `x.com/i/spaces/...` |
| Apple Podcasts | `podcasts.apple.com/...` |
| Spotify | `open.spotify.com/...` |
| YouTube | `youtube.com/watch?v=...` |
| 小宇宙 | `xiaoyuzhoufm.com/episode/...` |

### Video
| Platform | URL Pattern |
|----------|-------------|
| X/Twitter | `x.com/user/status/...` |
| YouTube | `youtube.com/watch?v=...` |
| Instagram | `instagram.com/reel/...`, `instagram.com/p/...` |
| 小红书 | `xiaohongshu.com/explore/...`, `xhslink.com/...` |

## Configuration

Create `.env`:

```env
# Server
HOST=127.0.0.1            # Use 0.0.0.0 to expose to network
PORT=8000
DOWNLOAD_DIR=./output

# API Authentication (optional)
# API_KEY=your-secret-key  # If set, requires X-API-Key header

# Optional
TELEGRAM_BOT_TOKEN=xxx
HUGGINGFACE_TOKEN=hf_xxx  # For speaker diarization

# Queue & Scheduling
QUEUE_ENABLED=true
MAX_CONCURRENT_QUEUE_JOBS=5
SCHEDULER_ENABLED=true
SCHEDULER_CHECK_INTERVAL=60

# Webhooks
DEFAULT_WEBHOOK_URL=https://your-webhook.com/hook
WEBHOOK_RETRY_ATTEMPTS=3
WEBHOOK_RETRY_DELAY=60
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
- [Queue & Scheduling](docs/queue-scheduling.md) - Batch downloads, priority queue, scheduling
- [Webhooks & Annotations](docs/webhooks-annotations.md) - Notifications and collaboration

## License

MIT
