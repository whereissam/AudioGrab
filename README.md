# X (Twitter) Spaces Downloader

Download and convert Twitter/X Spaces audio recordings.

## Features

- **Download Spaces** - Download any public Space with replay enabled
- **Format Conversion** - Convert between m4a, mp3, mp4, wav, flac, ogg
- **CLI Tool** - Simple command-line interface
- **REST API** - FastAPI backend for integrations
- **Telegram Bot** - Download via Telegram chat

## Requirements

- Python 3.10+
- FFmpeg
- yt-dlp

```bash
# macOS
brew install ffmpeg yt-dlp
```

## Installation

```bash
cd xdownloader
uv sync
```

## Usage

### Download a Space

```bash
# Download as m4a (default)
uv run xdownloader https://x.com/i/spaces/1vOxwdyYrlqKB

# Download as mp3
uv run xdownloader download -f mp3 https://x.com/i/spaces/...

# Custom output path
uv run xdownloader download -o my_space.m4a https://x.com/i/spaces/...
```

### Convert Audio Format

```bash
# Convert m4a to mp3
uv run xdownloader convert -f mp3 space.m4a

# Convert to mp4
uv run xdownloader convert -f mp4 space.m4a

# Convert to wav (lossless)
uv run xdownloader convert -f wav space.m4a

# Convert with custom quality
uv run xdownloader convert -f mp3 -q highest space.m4a

# Delete original after conversion
uv run xdownloader convert -f mp3 --delete-original space.m4a
```

**Supported formats:** mp3, mp4, aac, wav, ogg, flac

**Quality presets:** low (64k), medium (128k), high (192k), highest (320k)

### Run API Server

```bash
uv run xdownloader-api
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Run Telegram Bot

```bash
# Set TELEGRAM_BOT_TOKEN in .env first
uv run xdownloader-bot
```

### Python Library

```python
import asyncio
from app.core import SpaceDownloader
from app.core.converter import AudioConverter

async def main():
    # Download
    downloader = SpaceDownloader()
    result = await downloader.download(
        url="https://x.com/i/spaces/1vOxwdyYrlqKB",
        format="m4a"
    )
    print(f"Downloaded: {result.file_path}")

    # Convert
    converter = AudioConverter()
    mp3_path = await converter.convert(
        input_path=result.file_path,
        output_format="mp3",
        quality="high"
    )
    print(f"Converted: {mp3_path}")

asyncio.run(main())
```

## Project Structure

```
xdownloader/
├── app/
│   ├── core/
│   │   ├── downloader.py   # yt-dlp based downloader
│   │   ├── converter.py    # FFmpeg audio converter
│   │   ├── parser.py       # URL parsing
│   │   └── exceptions.py
│   ├── api/                # FastAPI REST API
│   ├── bot/                # Telegram bot
│   ├── cli.py              # CLI interface
│   └── main.py             # API entry point
├── docs/                   # Documentation
├── tests/
└── pyproject.toml
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/download` | Start download job |
| GET | `/api/download/{job_id}` | Get job status |
| GET | `/api/download/{job_id}/file` | Download file |

## Authentication

**No authentication needed** for public Spaces with replay enabled.

For private Spaces, set cookies in `.env`:
```env
TWITTER_AUTH_TOKEN=your_auth_token
TWITTER_CT0=your_ct0_cookie
```

## Documentation

See [docs/](./docs/) for detailed documentation.

## License

MIT
