# X Spaces Downloader - Frontend

<p align="center">
  <img src="public/xdownlader-brand.webp" alt="xdownloader" width="200">
</p>

Modern React frontend for downloading Twitter/X Spaces audio recordings.

## Tech Stack

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TanStack Router** - Type-safe routing
- **TailwindCSS v4** - Utility-first CSS framework
- **shadcn/ui** - Component library

## Getting Started

### Prerequisites

- Node.js 20.19.0+ or 22.12.0+
- bun, yarn, or bun

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
│   └── ui/              # shadcn/ui components
├── lib/
│   └── utils.ts         # Utility functions
├── routes/
│   ├── __root.tsx       # Root layout
│   └── index.tsx        # Home page (downloader)
├── main.tsx
└── index.css            # Theme configuration
```

## Features

- Download X Spaces as M4A, MP3, or MP4
- Real-time download progress
- Dark/light theme support
- Responsive design

## API Integration

The frontend communicates with the backend API:

| Endpoint | Description |
|----------|-------------|
| `POST /api/download` | Start download job |
| `GET /api/download/{job_id}` | Get job status |
| `GET /api/download/{job_id}/file` | Download file |

## License

MIT
