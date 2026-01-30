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
│   └── downloader/      # Download & transcription components
│       ├── DownloadForm.tsx
│       ├── TranscribeForm.tsx
│       ├── SuccessViews.tsx
│       └── types.ts
├── lib/
│   └── utils.ts         # Utility functions
├── routes/
│   ├── __root.tsx       # Root layout
│   └── index.tsx        # Home page (Audio/Video/Transcribe tabs)
├── main.tsx
└── index.css            # Theme configuration
```

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

## License

MIT
