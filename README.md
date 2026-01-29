# X (Twitter) Spaces Downloader

A Python backend for downloading Twitter/X Spaces audio recordings.

## Features

- **Core Library**: Async Python module for downloading Spaces
- **REST API**: FastAPI backend for web integrations
- **Telegram Bot**: Download Spaces directly via Telegram
- **CLI Tool**: Command-line interface for quick downloads

## Requirements

- Python 3.10+
- FFmpeg (must be in system PATH)
- Valid Twitter/X authentication cookies

## Installation

```bash
# Clone the repository
cd xdownloader

# Install dependencies with uv
uv sync

# Or install in development mode
uv sync --dev
```

## Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and add your Twitter cookies:

```env
TWITTER_AUTH_TOKEN=your_auth_token_here
TWITTER_CT0=your_ct0_cookie_here
```

### Getting Cookies

1. Log into Twitter/X in your browser
2. Open DevTools (F12)
3. Go to Application → Cookies → x.com
4. Copy `auth_token` and `ct0` values

## Usage

### CLI

```bash
# Basic download
uv run xdownloader https://x.com/i/spaces/1vOxwdyYrlqKB

# Download as MP3
uv run xdownloader -f mp3 https://x.com/i/spaces/1vOxwdyYrlqKB

# With custom output path
uv run xdownloader -o my_space.m4a https://x.com/i/spaces/1vOxwdyYrlqKB
```

### FastAPI Server

```bash
# Run the API server
uv run xdownloader-api

# Or with uvicorn directly
uv run uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000` with docs at `/docs`.

### Telegram Bot

```bash
# Set bot token in .env
# TELEGRAM_BOT_TOKEN=your_bot_token

# Run the bot
uv run xdownloader-bot
```

### Python Library

```python
import asyncio
from app.core import SpaceDownloader

async def main():
    downloader = SpaceDownloader()
    result = await downloader.download(
        url="https://x.com/i/spaces/1vOxwdyYrlqKB",
        format="m4a"
    )

    if result.success:
        print(f"Downloaded: {result.file_path}")
    else:
        print(f"Error: {result.error}")

asyncio.run(main())
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/download` | Start download job |
| GET | `/api/download/{job_id}` | Get job status |
| GET | `/api/download/{job_id}/file` | Download file |
| GET | `/api/space/{space_id}/metadata` | Get Space metadata |

## Project Structure

```
xdownloader/
├── app/
│   ├── core/           # Core download functionality
│   │   ├── auth.py     # Authentication handling
│   │   ├── client.py   # Twitter API client
│   │   ├── downloader.py
│   │   ├── merger.py   # FFmpeg audio processing
│   │   └── parser.py   # URL/response parsing
│   ├── api/            # FastAPI backend
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── bot/            # Telegram bot
│   │   └── bot.py
│   ├── cli.py          # CLI interface
│   ├── config.py       # Configuration
│   └── main.py         # FastAPI app
├── docs/               # Documentation
├── tests/              # Test suite
└── pyproject.toml      # Project config & dependencies
```

## Documentation

See the [docs](./docs/) folder for detailed documentation:

- [API Endpoints Reference](./docs/api-endpoints.md)
- [Authentication Guide](./docs/authentication.md)
- [Architecture Details](./docs/architecture.md)
- [Deployment Guide](./docs/deployment.md)

## Testing

```bash
uv run pytest tests/
```

## License

MIT
