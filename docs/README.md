# AudioGrab Backend

A Python backend service for downloading audio and video from X Spaces, Apple Podcasts, Spotify, YouTube, Discord, Instagram, 小红书, and more.

## Overview

This project provides:
- **CLI Tool**: Download audio/video and convert formats
- **Core Library**: Python module for programmatic access
- **FastAPI Backend**: REST API for web integrations
- **Real-Time Transcription**: WebSocket-based live audio transcription from microphone
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

## Features

### Real-Time Transcription

Transcribe audio from your browser microphone in real-time:

```
Browser Microphone → WebSocket → faster-whisper → Live Transcript
```

- **WebSocket streaming** at `/api/transcribe/live`
- **Context-aware transcription** using recent text as prompt
- **Smart segment merging** to handle chunk boundaries
- **Optional LLM polish** for cleaner output (requires AI provider)

Access via the `/live` route in the web UI.

## Documentation

- [Architecture Details](./architecture.md) (includes real-time transcription flow)
- [Deployment Guide](./deployment.md)
- [API Reference](./api-endpoints.md) (REST & WebSocket endpoints)
- [Authentication Guide](./authentication.md) (for private Spaces)
- [Queue & Scheduling](./queue-scheduling.md) (batch downloads, priority queue)
- [Webhooks & Annotations](./webhooks-annotations.md) (notifications, collaboration)

## License

MIT
