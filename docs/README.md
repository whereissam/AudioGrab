# X (Twitter) Spaces Downloader Backend

A Python backend service for downloading Twitter/X Spaces audio recordings.

## Overview

This project provides:
- **Core Library**: Python module for downloading X Spaces programmatically
- **FastAPI Backend**: REST API for integration with web/mobile clients
- **Telegram Bot**: Bot interface for easy Space downloads via chat

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Telegram Bot  │     │   Web Client    │     │  Chrome Ext     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────┬───────┴───────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   FastAPI Backend   │
              │   /api/download     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Core Downloader   │
              │   - Auth Handler    │
              │   - API Client      │
              │   - Stream Merger   │
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ X GraphQL   │  │ Stream API  │  │   FFmpeg    │
│ AudioSpace  │  │ live_video  │  │   Merger    │
│   ById      │  │   _stream   │  │             │
└─────────────┘  └─────────────┘  └─────────────┘
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TWITTER_AUTH_TOKEN="your_auth_token"
export TWITTER_CT0="your_ct0_cookie"

# Run the backend
uvicorn app.main:app --reload

# Or run the Telegram bot
python -m app.bot
```

## Documentation

- [API Endpoints Reference](./api-endpoints.md)
- [Authentication Guide](./authentication.md)
- [Architecture Details](./architecture.md)
- [Deployment Guide](./deployment.md)

## Requirements

- Python 3.10+
- FFmpeg (must be in PATH)
- Valid X/Twitter authentication cookies

## License

MIT
