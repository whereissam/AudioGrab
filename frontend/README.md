# AudioGrab - Frontend

<p align="center">
  <img src="public/logo.svg" alt="AudioGrab" width="200">
</p>

Modern React frontend for downloading, transcribing, and analyzing audio from X Spaces, YouTube, Apple Podcasts, Spotify, and more.

## Tech Stack

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TanStack Router** - Type-safe routing
- **TailwindCSS v4** - Utility-first CSS framework
- **shadcn/ui** - Component library
- **Radix UI** - Accessible components

## Getting Started

### Prerequisites

- Node.js 20.19.0+ or 22.12.0+
- bun, yarn, or npm

### Installation

```bash
bun install
```

### Development

```bash
bun run dev
# Frontend available at http://localhost:5173
```

Make sure the backend API is running at http://localhost:8000.

### Build

```bash
bun run build
bun run preview
```

## Project Structure

```
src/
├── components/
│   ├── ui/              # shadcn/ui components (Button, Input, Tabs)
│   ├── downloader/      # Download & transcription components
│   │   ├── DownloadForm.tsx
│   │   ├── TranscribeForm.tsx
│   │   ├── SuccessViews.tsx
│   │   └── types.ts
│   ├── clips/           # Viral clip generation
│   │   └── ClipsPage.tsx
│   ├── settings/        # Settings components
│   │   ├── AISettings.tsx
│   │   └── TranslationSettings.tsx
│   └── subscriptions/   # Subscription management components
│       ├── SubscriptionList.tsx
│       ├── SubscriptionCard.tsx
│       ├── SubscriptionDetail.tsx
│       ├── AddSubscriptionForm.tsx
│       └── types.ts
├── lib/
│   └── utils.ts         # Utility functions
├── routes/              # File-based routing (TanStack Router)
│   ├── __root.tsx       # Root layout with navigation
│   ├── index.tsx        # Redirects to /audio
│   ├── audio.tsx        # Audio download page
│   ├── video.tsx        # Video download page
│   ├── transcribe.tsx   # Transcription page
│   ├── clips.tsx        # Viral clips generation page
│   ├── settings.tsx     # Settings page
│   └── subscriptions.tsx # Subscriptions page
├── main.tsx
└── index.css            # Theme configuration
```

## Routes

| Route | Description |
|-------|-------------|
| `/audio` | Audio download (X Spaces, Podcasts, Spotify, YouTube, 小宇宙) |
| `/video` | Video download (X/Twitter, YouTube) |
| `/transcribe` | Transcription with Whisper models |
| `/clips` | Generate viral clips from transcriptions |
| `/settings` | AI provider, translation, and general settings |
| `/subscriptions` | RSS/YouTube subscription management |

## Features

### Download
- **Multi-platform support** - X Spaces, Apple Podcasts, Spotify, YouTube, 小宇宙
- **Audio & Video tabs** - Download audio or video separately
- **Format selection** - M4A, MP3, MP4 (platform-dependent)
- **Quality options** - 480p, 720p, 1080p for video

### Transcription
- **URL or file upload** - Transcribe from any supported URL or upload local files
- **Whisper model selection** - Tiny, Base, Small, Medium, Large-v3, Turbo
- **Output formats** - Text, SRT, VTT, JSON, Dialogue
- **Speaker diarization** - Identify different speakers (toggle + number of speakers)
- **Speaker renaming** - Rename "Speaker 0" to "Host", "Guest", etc.

### Subscriptions
- **RSS/Podcast feeds** - Subscribe to Apple Podcasts or any RSS feed
- **YouTube channels** - Auto-download new videos from channels
- **YouTube playlists** - Monitor playlists for new content
- **Auto-transcription** - Optionally transcribe downloads automatically
- **Download limits** - Keep only the last N downloads, auto-cleanup old files
- **Manual check** - Force check for new content anytime

### General
- **Real-time progress** - Live status updates during processing
- **Dark/light theme** - System preference or manual toggle
- **Responsive design** - Works on mobile and desktop
- **Copy & download** - Copy transcript to clipboard or download as file

## Supported Platforms

| Platform | Audio | Video | Transcribe |
|----------|-------|-------|------------|
| X Spaces | M4A, MP3 | - | Yes |
| X/Twitter | - | MP4 | Yes |
| YouTube | M4A, MP3 | MP4 | Yes |
| Apple Podcasts | M4A, MP3 | - | Yes |
| Spotify | MP3, M4A | - | Yes |
| 小宇宙 | M4A, MP3 | - | Yes |

## API Integration

The frontend communicates with the backend API:

### Download & Transcribe

| Endpoint | Description |
|----------|-------------|
| `POST /api/download` | Start download job |
| `GET /api/download/{job_id}` | Get job status |
| `GET /api/download/{job_id}/file` | Download file |
| `POST /api/transcribe` | Start transcription from URL |
| `POST /api/transcribe/upload` | Upload file & transcribe |
| `GET /api/transcribe/{job_id}` | Get transcription status |
| `GET /api/add?url=...` | Quick add (browser extension) |
| `GET /api/health` | Check service availability |

### Subscriptions

| Endpoint | Description |
|----------|-------------|
| `POST /api/subscriptions` | Create subscription |
| `GET /api/subscriptions` | List all subscriptions |
| `GET /api/subscriptions/{id}` | Get subscription details |
| `PATCH /api/subscriptions/{id}` | Update subscription |
| `DELETE /api/subscriptions/{id}` | Delete subscription |
| `POST /api/subscriptions/{id}/check` | Force check for new content |
| `GET /api/subscriptions/{id}/items` | List subscription items |
| `POST /api/subscriptions/{id}/items/{item_id}/retry` | Retry failed item |

## License

MIT
