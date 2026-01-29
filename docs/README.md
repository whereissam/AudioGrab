# X (Twitter) Spaces Downloader Backend

A Python backend service for downloading and converting Twitter/X Spaces audio recordings.

## Overview

This project provides:
- **CLI Tool**: Download Spaces and convert audio formats
- **Core Library**: Python module for programmatic access
- **FastAPI Backend**: REST API for web integrations
- **Telegram Bot**: Bot interface for easy downloads via chat

## How It Works

The downloader uses **yt-dlp** under the hood, which handles:
1. Extracting Space ID from URL
2. Fetching metadata via Twitter's GraphQL API
3. Getting the m3u8 stream URL
4. Downloading and merging HLS segments with FFmpeg

```
URL → yt-dlp → GraphQL API → m3u8 playlist → FFmpeg → audio file
```

## Quick Start

```bash
# Install dependencies
uv sync

# Download a Space (no auth needed for public Spaces)
uv run xdownloader https://x.com/i/spaces/1vOxwdyYrlqKB

# Download as MP3
uv run xdownloader download -f mp3 https://x.com/i/spaces/...

# Convert existing file
uv run xdownloader convert -f mp3 space.m4a
uv run xdownloader convert -f mp4 space.m4a
```

## Requirements

- Python 3.10+
- FFmpeg (for audio processing)
- yt-dlp (for downloading)

Install on macOS:
```bash
brew install ffmpeg yt-dlp
```

## Documentation

- [Architecture Details](./architecture.md)
- [Deployment Guide](./deployment.md)
- [API Reference](./api-endpoints.md) (for direct API usage)
- [Authentication Guide](./authentication.md) (for private Spaces)

## License

MIT
