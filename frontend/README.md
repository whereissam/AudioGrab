# AudioGrab - Frontend

<p align="center">
  <img src="public/logo.svg" alt="AudioGrab" width="200">
</p>

Modern React frontend for downloading audio from X Spaces, Apple Podcasts, and Spotify.

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
│   └── ui/              # shadcn/ui components (Button, Input, Tabs)
├── lib/
│   └── utils.ts         # Utility functions
├── routes/
│   ├── __root.tsx       # Root layout
│   └── index.tsx        # Home page (multi-platform downloader)
├── main.tsx
└── index.css            # Theme configuration
```

## Features

- **Multi-platform support** - Tabs for X Spaces, Apple Podcasts, Spotify
- **Format selection** - M4A, MP3, MP4 (platform-dependent)
- **Real-time download progress**
- **Dark/light theme support**
- **Responsive design**

## Supported Platforms

| Platform | Formats | Notes |
|----------|---------|-------|
| X Spaces | M4A, MP3, MP4 | Uses yt-dlp |
| Apple Podcasts | M4A, MP3 | Direct RSS download |
| Spotify | MP3, M4A | Uses spotDL (YouTube matching) |

## API Integration

The frontend communicates with the backend API:

| Endpoint | Description |
|----------|-------------|
| `POST /api/download` | Start download job |
| `GET /api/download/{job_id}` | Get job status |
| `GET /api/download/{job_id}/file` | Download file |
| `GET /api/platforms` | List supported platforms |

## License

MIT
