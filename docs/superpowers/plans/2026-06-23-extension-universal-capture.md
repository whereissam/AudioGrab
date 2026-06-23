# Universal Capture Browser Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Sift browser extension auto-detect audio/video on any page (DOM + network sniffing), let the user pick mp3/mp4 + quality in the popup, and save the converted file to the browser's Downloads folder — backed by a new server-side generic downloader and a format-aware capture endpoint.

**Architecture:** The extension is a detector + thin client; the Sift server does all download/convert/tag work via yt-dlp + ffmpeg. A new `GenericDownloader` slots into the existing `DownloaderFactory` as the lowest-priority fallback so arbitrary URLs/streams work. A new `POST /api/capture` endpoint carries format/quality and routes to a specific platform or the generic fallback; the existing `GET /api/download/{job_id}/file` serves the result to the browser.

**Tech Stack:** Python 3 / FastAPI / yt-dlp / ffmpeg (server, tested with pytest via `uv run pytest`); plain-JS MV3 browser extension (pure helper logic tested with `bun test`).

## Global Constraints

- Package management: `uv` for Python, `bun`/`bunx` for JS — never npm/yarn/npx/pip.
- All new features must include tests in the appropriate test directory (`tests/` for Python, `browser-extension/tests/` for JS).
- Only `git add` files modified in the current task — never stage all files.
- Conventional commit messages (`feat:`, `fix:`, `docs:`, etc.). End commit messages with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Server work spans `app/core/` (logic) and `app/api/` (HTTP); follow the existing `PlatformDownloader` contract and router patterns.
- The extension must remain build-step-free: pure helper logic lives in `browser-extension/lib/*.js` files that define top-level functions (global in classic-script context) AND `module.exports` them at the bottom for `bun test`.
- Privacy rule (hard): the extension stores only media-typed URLs, in-memory per-tab, never persisted; nothing leaves the browser until the user clicks convert, and only the chosen URL + format/quality are sent.
- Auth: `POST /api/capture` and the file endpoint require `X-API-Key` when `API_KEY` is configured (the `download_routes` router already enforces `verify_api_key`).

---

## Phase 1 — Server foundation

### Task 1: Add `Platform.GENERIC` enum value

**Files:**
- Modify: `app/core/base.py` (Platform enum, after `XIAOHONGSHU = "xiaohongshu"`)
- Modify: `app/api/schemas.py` (Platform enum, after `XIAOHONGSHU = "xiaohongshu"`)
- Modify: `app/api/download_routes.py:34-48` (`_core_platform_to_schema` mapping)
- Test: `tests/test_generic_platform_enum.py`

**Interfaces:**
- Produces: `app.core.base.Platform.GENERIC` (value `"generic"`), `app.api.schemas.Platform.GENERIC` (value `"generic"`), and `_core_platform_to_schema(CorePlatform.GENERIC) == schemas.Platform.GENERIC`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generic_platform_enum.py
from app.core.base import Platform as CorePlatform
from app.api.schemas import Platform as SchemaPlatform
from app.api.download_routes import _core_platform_to_schema


def test_core_platform_has_generic():
    assert CorePlatform.GENERIC.value == "generic"


def test_schema_platform_has_generic():
    assert SchemaPlatform.GENERIC.value == "generic"


def test_core_generic_maps_to_schema_generic():
    assert _core_platform_to_schema(CorePlatform.GENERIC) == SchemaPlatform.GENERIC
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_generic_platform_enum.py -v`
Expected: FAIL with `AttributeError: GENERIC` (enum member missing).

- [ ] **Step 3: Add the enum members and mapping**

In `app/core/base.py`, add after the `XIAOHONGSHU = "xiaohongshu"` line:

```python
    GENERIC = "generic"  # Fallback: any URL handled via yt-dlp generic extractor
```

In `app/api/schemas.py`, add after the `XIAOHONGSHU = "xiaohongshu"` line (before `AUTO = "auto"`):

```python
    GENERIC = "generic"  # Fallback for arbitrary URLs / sniffed streams
```

In `app/api/download_routes.py`, add to the `mapping` dict inside `_core_platform_to_schema` (after the `CorePlatform.XIAOHONGSHU` entry):

```python
        CorePlatform.GENERIC: Platform.GENERIC,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_generic_platform_enum.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/core/base.py app/api/schemas.py app/api/download_routes.py tests/test_generic_platform_enum.py
git commit -m "feat(capture): add Platform.GENERIC enum and schema mapping

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `GenericDownloader` fallback

**Files:**
- Create: `app/core/platforms/generic.py`
- Modify: `app/core/platforms/__init__.py` (export `GenericDownloader`)
- Modify: `app/core/downloader.py:20-46` (`_get_platform_downloaders` — import and append `GenericDownloader` **last**)
- Test: `tests/test_generic_downloader.py`

**Interfaces:**
- Consumes: `Platform.GENERIC` (Task 1); base classes `PlatformDownloader`, `AudioMetadata`, `DownloadResult` from `app.core.base`.
- Produces: `GenericDownloader` with `PLATFORM = Platform.GENERIC`, classmethods `can_handle_url(url) -> bool` (True for any `http://`/`https://` URL), `is_available() -> bool` (yt-dlp on PATH), `extract_content_id(url) -> str`, and `async download(url, output_path=None, output_format="mp3", quality="high") -> DownloadResult`. Because it is registered last and matches any http(s) URL, `DownloaderFactory.get_downloader(url)` returns it only when no specific platform matches.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_generic_downloader.py
from app.core.base import Platform
from app.core.platforms.generic import GenericDownloader
from app.core.downloader import DownloaderFactory


def test_can_handle_any_http_url():
    assert GenericDownloader.can_handle_url("https://example.com/some/video")
    assert GenericDownloader.can_handle_url("http://cdn.example.net/stream.m3u8")


def test_does_not_handle_non_http():
    assert not GenericDownloader.can_handle_url("ftp://example.com/x")
    assert not GenericDownloader.can_handle_url("not a url")


def test_platform_attribute_is_generic():
    assert GenericDownloader.PLATFORM == Platform.GENERIC


def test_specific_platform_still_wins_over_generic():
    # A YouTube URL must resolve to the YouTube platform, not GENERIC.
    detected = DownloaderFactory.detect_platform("https://www.youtube.com/watch?v=abc123")
    assert detected != Platform.GENERIC


def test_unknown_url_resolves_to_generic_downloader():
    dl = DownloaderFactory.get_downloader("https://example.com/random/page")
    assert isinstance(dl, GenericDownloader)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_generic_downloader.py -v`
Expected: FAIL with `ModuleNotFoundError: app.core.platforms.generic`.

- [ ] **Step 3: Create the GenericDownloader**

Create `app/core/platforms/generic.py`:

```python
"""Generic fallback downloader using yt-dlp's universal extractor.

Handles any http(s) URL that no specific platform downloader claims:
page URLs (yt-dlp picks an extractor), HLS/DASH manifests (.m3u8/.mpd),
and direct media files (.mp4/.mp3/.m4a). Registered LAST in the factory.
"""

import asyncio
import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Optional

from ...config import get_settings
from ..base import Platform, PlatformDownloader, AudioMetadata, DownloadResult
from ..exceptions import SiftError, ContentNotFoundError, ToolNotFoundError

logger = logging.getLogger(__name__)


class GenericDownloader(PlatformDownloader):
    """Last-resort downloader for arbitrary URLs and sniffed media streams."""

    PLATFORM = Platform.GENERIC

    def __init__(self, download_dir: Optional[Path] = None):
        self.settings = get_settings()
        self.download_dir = Path(download_dir) if download_dir else self.settings.get_download_path()
        self._yt_dlp_path = shutil.which("yt-dlp")

    @property
    def platform(self) -> Platform:
        return Platform.GENERIC

    @classmethod
    def can_handle_url(cls, url: str) -> bool:
        return isinstance(url, str) and url.strip().lower().startswith(("http://", "https://"))

    @classmethod
    def extract_content_id(cls, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:16]

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("yt-dlp") is not None

    def _build_cmd(self, url: str, output_template: str, output_format: str, quality: str) -> list[str]:
        """Build the yt-dlp command for audio (mp3/m4a/aac) or video (mp4)."""
        cmd = [self._yt_dlp_path, "--no-progress", "--print-json",
               "-o", output_template, "--concurrent-fragments", "16",
               "--fragment-retries", "5"]
        if output_format in ("mp3", "m4a", "aac"):
            cmd += ["-x", "--audio-format", output_format,
                    "--audio-quality", {"low": "9", "medium": "5", "high": "2", "highest": "0"}.get(quality, "2")]
        else:  # mp4 (video)
            format_spec = {
                "low": "worst",
                "medium": "best[height<=480]/best",
                "high": "best[height<=720]/best",
                "highest": "best",
            }.get(quality, "best")
            cmd += ["-f", format_spec, "--merge-output-format", "mp4", "--recode-video", "mp4"]
        cmd.append(url)
        return cmd

    async def download(self, url: str, output_path: Optional[Path] = None,
                       output_format: str = "mp3", quality: str = "high") -> DownloadResult:
        logger.info(f"Generic download: {url} -> {output_format}")
        if not self._yt_dlp_path:
            return DownloadResult(success=False, file_path=None, metadata=None,
                                  error="yt-dlp not found in PATH")
        try:
            content_id = self.extract_content_id(url)
            self.download_dir.mkdir(parents=True, exist_ok=True)
            output_template = str(output_path) if output_path else str(
                self.download_dir / "%(title).100s [%(id)s].%(ext)s")

            cmd = self._build_cmd(url, output_template, output_format, quality)
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"yt-dlp error: {error_msg[:500]}")
                if "Unsupported URL" in error_msg or "no video" in error_msg.lower():
                    raise ContentNotFoundError(f"No downloadable media at URL: {url}")
                raise SiftError(f"yt-dlp failed: {error_msg[:500]}")

            metadata, file_path = None, None
            for line in stdout.decode().strip().split("\n"):
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    file_path = Path(data.get("_filename", data.get("filename", "")))
                    metadata = AudioMetadata(
                        platform=Platform.GENERIC,
                        content_id=str(data.get("id", content_id)),
                        title=data.get("title") or data.get("webpage_url_basename") or "Untitled",
                        creator_name=data.get("uploader") or data.get("channel"),
                        creator_username=data.get("uploader_id") or data.get("channel_id"),
                        duration_seconds=data.get("duration"),
                        artwork_url=data.get("thumbnail"),
                        description=(data.get("description") or "")[:500] or None,
                    )
                    break

            # yt-dlp rewrites the extension after recode/extract; resolve actual file.
            if not file_path or not file_path.exists():
                candidates = sorted(self.download_dir.glob(f"*{content_id}*"),
                                    key=lambda f: f.stat().st_mtime, reverse=True)
                if not candidates:
                    candidates = sorted(self.download_dir.glob(f"*.{output_format}"),
                                        key=lambda f: f.stat().st_mtime, reverse=True)
                file_path = candidates[0] if candidates else None
            else:
                stem_match = sorted(self.download_dir.glob(f"{file_path.stem}.*"),
                                    key=lambda f: f.stat().st_mtime, reverse=True)
                if stem_match:
                    file_path = stem_match[0]

            if not file_path or not file_path.exists():
                raise SiftError("Download completed but output file not found")

            return DownloadResult(success=True, file_path=file_path, metadata=metadata,
                                  file_size_bytes=file_path.stat().st_size)
        except (ContentNotFoundError, SiftError) as e:
            logger.error(f"Generic download failed: {e}")
            return DownloadResult(success=False, file_path=None, metadata=None, error=str(e))
        except Exception as e:
            logger.exception(f"Unexpected generic download error: {e}")
            return DownloadResult(success=False, file_path=None, metadata=None,
                                  error=f"Unexpected error: {e}")

    async def get_metadata(self, url: str) -> Optional[AudioMetadata]:
        if not self._yt_dlp_path:
            return None
        try:
            cmd = [self._yt_dlp_path, "--no-download", "--print-json", url]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await process.communicate()
            if process.returncode != 0:
                return None
            for line in stdout.decode().strip().split("\n"):
                if line.startswith("{"):
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    return AudioMetadata(
                        platform=Platform.GENERIC,
                        content_id=str(data.get("id", self.extract_content_id(url))),
                        title=data.get("title") or "Untitled",
                        creator_name=data.get("uploader") or data.get("channel"),
                        duration_seconds=data.get("duration"),
                        artwork_url=data.get("thumbnail"),
                    )
            return None
        except Exception as e:
            logger.warning(f"Generic get_metadata failed: {e}")
            return None
```

- [ ] **Step 4: Export and register it (last)**

In `app/core/platforms/__init__.py`, add an import and include `GenericDownloader` in `__all__` (match the file's existing style — add `from .generic import GenericDownloader` and append `"GenericDownloader"` to `__all__`).

In `app/core/downloader.py`, inside `_get_platform_downloaders` (lines ~20-46): add `GenericDownloader` to the lazy import block AND append it as the **last** element of the `_platform_downloaders` list (after `XiaohongshuVideoDownloader`):

```python
        from .platforms import (
            XSpacesDownloader,
            ApplePodcastsDownloader,
            SpotifyDownloader,
            YouTubeDownloader,
            XiaoyuzhouDownloader,
            DiscordAudioDownloader,
            XVideoDownloader,
            YouTubeVideoDownloader,
            InstagramVideoDownloader,
            XiaohongshuVideoDownloader,
            GenericDownloader,
        )
        _platform_downloaders = [
            XSpacesDownloader,
            ApplePodcastsDownloader,
            SpotifyDownloader,
            YouTubeDownloader,
            XiaoyuzhouDownloader,
            DiscordAudioDownloader,
            XVideoDownloader,
            YouTubeVideoDownloader,
            InstagramVideoDownloader,
            XiaohongshuVideoDownloader,
            GenericDownloader,  # MUST stay last — matches any http(s) URL
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_generic_downloader.py -v`
Expected: PASS (5 passed). If `test_specific_platform_still_wins_over_generic` fails, GenericDownloader is not last in the list.

- [ ] **Step 6: Commit**

```bash
git add app/core/platforms/generic.py app/core/platforms/__init__.py app/core/downloader.py tests/test_generic_downloader.py
git commit -m "feat(capture): add GenericDownloader yt-dlp fallback (registered last)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `POST /api/capture` endpoint

**Files:**
- Modify: `app/api/schemas.py` (add `CaptureRequest` model near `DownloadRequest`)
- Modify: `app/api/download_routes.py` (add `capture` route; reuse `jobs`, `_process_download`, `_core_platform_to_schema`)
- Test: `tests/test_capture_endpoint.py`

**Interfaces:**
- Consumes: `validate_url_ssrf(url) -> tuple[bool, str | None]` from `app.core.url_validator`; `DownloadRequest`, `OutputFormat`, `QualityPreset` from `app.api.schemas`; `_process_download`, `jobs`, `DownloaderFactory` (already in `download_routes`).
- Produces: `POST /api/capture` accepting `{url: str, kind?: "page"|"stream"|"file", format?: "mp3"|"mp4", quality?: "low"|"medium"|"high"|"highest"}`; returns `{job_id: str, status: "pending", platform: str, download_url: str}` where `download_url == f"/api/download/{job_id}/file"`. Rejects SSRF-blocked URLs with HTTP 400.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture_endpoint.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_capture_rejects_ssrf_url():
    resp = client.post("/api/capture", json={"url": "http://169.254.169.254/latest/meta-data/"})
    assert resp.status_code == 400


def test_capture_rejects_non_http():
    resp = client.post("/api/capture", json={"url": "ftp://example.com/x"})
    assert resp.status_code == 400


def test_capture_accepts_arbitrary_url_and_queues_job(monkeypatch):
    # Don't actually run yt-dlp during the test — stub the background processor.
    import app.api.download_routes as dr

    async def fake_process(job_id, request):
        dr.jobs[job_id].status = dr.JobStatus.COMPLETED

    monkeypatch.setattr(dr, "_process_download", fake_process)
    resp = client.post("/api/capture", json={
        "url": "https://example.com/some/video", "format": "mp3", "quality": "high"})
    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["download_url"] == f"/api/download/{body['job_id']}/file"
    assert body["platform"] == "generic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_capture_endpoint.py -v`
Expected: FAIL with 404 (route not defined) on all three.

- [ ] **Step 3: Add the `CaptureRequest` schema**

In `app/api/schemas.py`, after the `DownloadRequest` class, add:

```python
class CaptureRequest(BaseModel):
    """Browser-extension capture: detect-and-convert any URL or sniffed stream."""

    url: str = Field(..., description="Page URL or sniffed media stream URL")
    kind: str = Field(default="page", description="page | stream | file (UI hint; server treats uniformly)")
    format: OutputFormat = Field(default=OutputFormat.MP3, description="Output format (mp3 audio or mp4 video)")
    quality: QualityPreset = Field(default=QualityPreset.HIGH, description="Quality preset")
```

- [ ] **Step 4: Add the route**

In `app/api/download_routes.py`, add the import near the top (after the existing `from .schemas import (...)` block, extend it to include `CaptureRequest`, and add):

```python
from ..core.url_validator import validate_url_ssrf
```

Then add this route (place it after the existing `_process_download` function and before the GET routes):

```python
@router.post("/capture")
async def capture(body: CaptureRequest, background_tasks: BackgroundTasks):
    """Detect-and-convert endpoint for the browser extension.

    Validates the URL against the SSRF allowlist, routes to a specific
    platform downloader or the generic yt-dlp fallback, and queues a
    download job converting to the requested format/quality.
    """
    ok, reason = validate_url_ssrf(body.url)
    if not ok:
        raise HTTPException(status_code=400, detail=f"URL rejected: {reason}")

    detected = DownloaderFactory.detect_platform(body.url)  # GENERIC for unknown URLs
    if detected is None:
        raise HTTPException(status_code=400, detail="No downloader can handle this URL")

    job_id = str(uuid.uuid4())
    job = DownloadJob(
        job_id=job_id,
        status=JobStatus.PENDING,
        platform=_core_platform_to_schema(detected),
        progress=0.0,
        created_at=datetime.utcnow(),
    )
    jobs[job_id] = job

    request = DownloadRequest(url=body.url, format=body.format, quality=body.quality)
    background_tasks.add_task(_process_download, job_id, request)

    return {
        "job_id": job_id,
        "status": "pending",
        "platform": job.platform.value,
        "download_url": f"/api/download/{job_id}/file",
    }
```

Note: ensure `DownloadRequest` and `CaptureRequest` are both imported in the `from .schemas import (...)` block at the top of the file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_capture_endpoint.py -v`
Expected: PASS (3 passed). If the SSRF test fails with 200, confirm `validate_url_ssrf` blocks link-local `169.254.169.254`.

- [ ] **Step 6: Run the full server suite**

Run: `uv run pytest tests/ -q`
Expected: PASS (no regressions). Fix any failures before committing.

- [ ] **Step 7: Commit**

```bash
git add app/api/schemas.py app/api/download_routes.py tests/test_capture_endpoint.py
git commit -m "feat(capture): add POST /api/capture endpoint (SSRF-checked, format-aware)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — Detection engine (extension)

### Task 4: Media-URL classifier helper (pure, tested)

**Files:**
- Create: `browser-extension/lib/detect.js`
- Create: `browser-extension/tests/detect.test.js`
- Create: `browser-extension/package.json` (so `bun test` runs in this dir)

**Interfaces:**
- Produces (all on the global scope in classic-script context, and `module.exports`ed for tests):
  - `classifyMediaUrl(url: string): {kind: "stream"|"file", mediaType: string} | null` — returns null for non-media URLs; `.m3u8`/`.mpd` → `kind:"stream"`; `.mp4`/`.m4a`/`.mp3`/`.aac`/`.webm` → `kind:"file"`; `.ts` segments → null (collapsed to playlist elsewhere).
  - `dedupeKey(candidate: {url: string}): string` — normalized key (strip hash, lowercase host).
  - `mergeCandidates(existing: object[], incoming: object[]): object[]` — dedupes by `dedupeKey`, preserves first-seen order.

- [ ] **Step 1: Write the failing test**

```javascript
// browser-extension/tests/detect.test.js
import { test, expect } from "bun:test";
const { classifyMediaUrl, dedupeKey, mergeCandidates } = require("../lib/detect.js");

test("classifies HLS manifest as stream", () => {
  expect(classifyMediaUrl("https://cdn.x.com/a/playlist.m3u8")).toEqual({ kind: "stream", mediaType: "hls" });
});

test("classifies direct mp4 as file", () => {
  expect(classifyMediaUrl("https://cdn.x.com/a/video.mp4?token=1")).toEqual({ kind: "file", mediaType: "mp4" });
});

test("ignores .ts segments", () => {
  expect(classifyMediaUrl("https://cdn.x.com/a/seg00001.ts")).toBeNull();
});

test("ignores non-media urls", () => {
  expect(classifyMediaUrl("https://x.com/home")).toBeNull();
});

test("dedupeKey strips fragment and lowercases host", () => {
  expect(dedupeKey({ url: "https://CDN.X.com/a/video.mp4#t=10" }))
    .toEqual(dedupeKey({ url: "https://cdn.x.com/a/video.mp4" }));
});

test("mergeCandidates dedupes and preserves order", () => {
  const a = [{ url: "https://x.com/1.mp4" }];
  const b = [{ url: "https://x.com/1.mp4" }, { url: "https://x.com/2.mp4" }];
  const merged = mergeCandidates(a, b);
  expect(merged.map((c) => c.url)).toEqual(["https://x.com/1.mp4", "https://x.com/2.mp4"]);
});
```

- [ ] **Step 2: Create package.json and run test to verify it fails**

Create `browser-extension/package.json`:

```json
{
  "name": "sift-extension",
  "private": true,
  "scripts": { "test": "bun test" }
}
```

Run: `cd browser-extension && bun test`
Expected: FAIL — `Cannot find module '../lib/detect.js'`.

- [ ] **Step 3: Implement the helper**

Create `browser-extension/lib/detect.js`:

```javascript
// Pure media-detection helpers. Loaded as a classic script in the extension
// (functions become global), and require()-able for bun tests.

const STREAM_EXT = { m3u8: "hls", mpd: "dash" };
const FILE_EXT = { mp4: "mp4", m4a: "m4a", mp3: "mp3", aac: "aac", webm: "webm" };

function _extension(url) {
  try {
    const u = new URL(url);
    const path = u.pathname.toLowerCase();
    const dot = path.lastIndexOf(".");
    return dot === -1 ? "" : path.slice(dot + 1);
  } catch {
    return "";
  }
}

function classifyMediaUrl(url) {
  const ext = _extension(url);
  if (!ext) return null;
  if (ext === "ts") return null; // HLS segment — collapse to its playlist
  if (STREAM_EXT[ext]) return { kind: "stream", mediaType: STREAM_EXT[ext] };
  if (FILE_EXT[ext]) return { kind: "file", mediaType: FILE_EXT[ext] };
  return null;
}

function dedupeKey(candidate) {
  try {
    const u = new URL(candidate.url);
    return `${u.protocol}//${u.host.toLowerCase()}${u.pathname}${u.search}`;
  } catch {
    return String(candidate.url);
  }
}

function mergeCandidates(existing, incoming) {
  const seen = new Map();
  const out = [];
  for (const c of [...existing, ...incoming]) {
    const k = dedupeKey(c);
    if (!seen.has(k)) {
      seen.set(k, true);
      out.push(c);
    }
  }
  return out;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { classifyMediaUrl, dedupeKey, mergeCandidates };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd browser-extension && bun test`
Expected: PASS (6 pass).

- [ ] **Step 5: Commit**

```bash
git add browser-extension/lib/detect.js browser-extension/tests/detect.test.js browser-extension/package.json
git commit -m "feat(ext): add pure media-URL classifier + dedupe helpers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Manifest permissions + content-script DOM scan

**Files:**
- Modify: `browser-extension/manifest.json`
- Modify: `browser-extension/manifest.firefox.json`
- Create: `browser-extension/lib/dom-scan.js`
- Rewrite: `browser-extension/content.js`
- Create: `browser-extension/tests/dom-scan.test.js`

**Interfaces:**
- Consumes: nothing from other tasks (pure DOM logic).
- Produces: `scanDomForMedia(doc: Document, pageUrl: string): object[]` (global + `module.exports`ed) returning candidates `{url, kind, mediaType, label, source:"dom"}`. Always includes a `kind:"page"` candidate for `pageUrl`. `content.js` calls it and posts `{type:"DOM_CANDIDATES", candidates}` to the background worker.

- [ ] **Step 1: Write the failing test**

```javascript
// browser-extension/tests/dom-scan.test.js
import { test, expect } from "bun:test";
const { scanDomForMedia } = require("../lib/dom-scan.js");

function fakeDoc(html) {
  // Minimal DOM stub: only the methods scanDomForMedia uses.
  const videos = [];
  const audios = [];
  const sources = [];
  const metas = [];
  return {
    querySelectorAll(sel) {
      if (sel === "video") return videos;
      if (sel === "audio") return audios;
      if (sel === "source") return sources;
      if (sel.startsWith("meta")) return metas;
      return [];
    },
    _videos: videos, _audios: audios, _sources: sources, _metas: metas,
  };
}

test("always includes the page url as a page candidate", () => {
  const out = scanDomForMedia(fakeDoc(""), "https://example.com/watch");
  expect(out.some((c) => c.kind === "page" && c.url === "https://example.com/watch")).toBe(true);
});

test("captures a video src as a file candidate", () => {
  const doc = fakeDoc("");
  doc._videos.push({ getAttribute: (a) => (a === "src" ? "https://cdn.example.com/v.mp4" : null) });
  const out = scanDomForMedia(doc, "https://example.com/watch");
  expect(out.some((c) => c.url === "https://cdn.example.com/v.mp4" && c.kind === "file")).toBe(true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd browser-extension && bun test tests/dom-scan.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `scanDomForMedia`**

Create `browser-extension/lib/dom-scan.js`:

```javascript
// Pure DOM media scanner. Depends on classifyMediaUrl from detect.js when
// running in the extension (both loaded as classic scripts). For tests we
// require detect.js directly.
let _classify;
if (typeof classifyMediaUrl === "function") {
  _classify = classifyMediaUrl; // extension global
} else {
  _classify = require("./detect.js").classifyMediaUrl; // bun test
}

function _labelFor(kind, mediaType, url) {
  let host = "";
  try { host = new URL(url).host; } catch { host = ""; }
  if (kind === "page") return `Page — ${host}`;
  if (kind === "stream") return `${mediaType.toUpperCase()} stream — ${host}`;
  return `Direct ${mediaType} — ${host}`;
}

function scanDomForMedia(doc, pageUrl) {
  const out = [{ url: pageUrl, kind: "page", mediaType: "page",
                 label: _labelFor("page", "page", pageUrl), source: "dom" }];
  const push = (url) => {
    if (!url) return;
    const cls = _classify(url);
    if (!cls) return;
    out.push({ url, kind: cls.kind, mediaType: cls.mediaType,
               label: _labelFor(cls.kind, cls.mediaType, url), source: "dom" });
  };
  for (const v of doc.querySelectorAll("video")) push(v.getAttribute("src"));
  for (const a of doc.querySelectorAll("audio")) push(a.getAttribute("src"));
  for (const s of doc.querySelectorAll("source")) push(s.getAttribute("src"));
  for (const m of doc.querySelectorAll('meta[property="og:video"], meta[property="og:audio"], meta[name="twitter:player:stream"]')) {
    push(m.getAttribute("content"));
  }
  return out;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { scanDomForMedia };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd browser-extension && bun test tests/dom-scan.test.js`
Expected: PASS (2 pass).

- [ ] **Step 5: Rewrite `content.js` to use the scanner**

Replace `browser-extension/content.js` with:

```javascript
// Content script: scans the DOM for media and reports to the background worker.
// lib/detect.js and lib/dom-scan.js are loaded before this file (see manifest).

function reportCandidates() {
  try {
    const candidates = scanDomForMedia(document, window.location.href);
    chrome.runtime.sendMessage({ type: "DOM_CANDIDATES", candidates });
  } catch (e) {
    // Never throw into the page.
  }
}

reportCandidates();

// Re-scan on SPA navigation and on DOM mutations (debounced).
let lastUrl = window.location.href;
let debounce = null;
const observer = new MutationObserver(() => {
  const changed = window.location.href !== lastUrl;
  if (changed) lastUrl = window.location.href;
  clearTimeout(debounce);
  debounce = setTimeout(reportCandidates, changed ? 0 : 1500);
});
observer.observe(document.body, { childList: true, subtree: true });
```

- [ ] **Step 6: Update both manifests**

In `browser-extension/manifest.json`: set `permissions` to `["activeTab", "storage", "webRequest", "downloads"]`; add `host_permissions` `["<all_urls>"]`; change the single `content_scripts` entry so `matches` is `["<all_urls>"]` and `js` is `["lib/detect.js", "lib/dom-scan.js", "content.js"]`.

```json
  "permissions": ["activeTab", "storage", "webRequest", "downloads"],
  "host_permissions": ["<all_urls>"],
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["lib/detect.js", "lib/dom-scan.js", "content.js"],
      "run_at": "document_idle"
    }
  ],
```

Apply the equivalent edits to `browser-extension/manifest.firefox.json` (same `permissions`, `host_permissions`, `content_scripts`; keep its existing MV2/MV3 structure otherwise).

- [ ] **Step 7: Commit**

```bash
git add browser-extension/manifest.json browser-extension/manifest.firefox.json browser-extension/lib/dom-scan.js browser-extension/content.js browser-extension/tests/dom-scan.test.js
git commit -m "feat(ext): DOM media scan + broaden manifest permissions for sniffing

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Background sniffing + per-tab registry

**Files:**
- Create: `browser-extension/lib/registry.js`
- Rewrite: `browser-extension/background.js`
- Create: `browser-extension/tests/registry.test.js`

**Interfaces:**
- Consumes: `classifyMediaUrl`, `mergeCandidates`, `dedupeKey` from `lib/detect.js`.
- Produces: `lib/registry.js` exporting `createRegistry()` returning an object with `addForTab(tabId, candidates)`, `getForTab(tabId): object[]`, `clearTab(tabId)`, and `count(tabId): number`. `background.js` wires `chrome.webRequest.onBeforeRequest` (network candidates), the `DOM_CANDIDATES` message (from content.js), a `GET_CANDIDATES` responder (for the popup), and badge updates.

- [ ] **Step 1: Write the failing test**

```javascript
// browser-extension/tests/registry.test.js
import { test, expect } from "bun:test";
const { createRegistry } = require("../lib/registry.js");

test("adds and retrieves per-tab candidates", () => {
  const r = createRegistry();
  r.addForTab(1, [{ url: "https://x.com/1.mp4" }]);
  r.addForTab(1, [{ url: "https://x.com/2.mp4" }]);
  expect(r.getForTab(1).map((c) => c.url)).toEqual(["https://x.com/1.mp4", "https://x.com/2.mp4"]);
});

test("dedupes within a tab", () => {
  const r = createRegistry();
  r.addForTab(1, [{ url: "https://x.com/1.mp4" }]);
  r.addForTab(1, [{ url: "https://x.com/1.mp4" }]);
  expect(r.count(1)).toBe(1);
});

test("isolates tabs and clears", () => {
  const r = createRegistry();
  r.addForTab(1, [{ url: "https://x.com/1.mp4" }]);
  r.addForTab(2, [{ url: "https://x.com/2.mp4" }]);
  expect(r.count(2)).toBe(1);
  r.clearTab(1);
  expect(r.count(1)).toBe(0);
  expect(r.count(2)).toBe(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd browser-extension && bun test tests/registry.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the registry**

Create `browser-extension/lib/registry.js`:

```javascript
let _merge;
if (typeof mergeCandidates === "function") {
  _merge = mergeCandidates; // extension global
} else {
  _merge = require("./detect.js").mergeCandidates; // bun test
}

function createRegistry() {
  const byTab = new Map(); // tabId -> candidate[]
  return {
    addForTab(tabId, candidates) {
      const existing = byTab.get(tabId) || [];
      byTab.set(tabId, _merge(existing, candidates || []));
    },
    getForTab(tabId) {
      return byTab.get(tabId) || [];
    },
    clearTab(tabId) {
      byTab.delete(tabId);
    },
    count(tabId) {
      return (byTab.get(tabId) || []).length;
    },
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { createRegistry };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd browser-extension && bun test tests/registry.test.js`
Expected: PASS (3 pass).

- [ ] **Step 5: Rewrite `background.js`**

Replace `browser-extension/background.js` with (the service worker must be an ES/importScripts module — use `importScripts` for classic SW):

```javascript
// Background service worker: network sniffing + per-tab media registry.
importScripts("lib/detect.js", "lib/registry.js");

const registry = createRegistry();

function refreshBadge(tabId) {
  const n = registry.count(tabId);
  chrome.action.setBadgeText({ text: n ? String(n) : "", tabId });
  chrome.action.setBadgeBackgroundColor({ color: "#6366f1", tabId });
}

// Network sniffing (observe-only).
chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    if (details.tabId < 0) return;
    const cls = classifyMediaUrl(details.url);
    if (!cls) return;
    let host = "";
    try { host = new URL(details.url).host; } catch {}
    const label = cls.kind === "stream"
      ? `${cls.mediaType.toUpperCase()} stream — ${host}`
      : `Direct ${cls.mediaType} — ${host}`;
    registry.addForTab(details.tabId, [{
      url: details.url, kind: cls.kind, mediaType: cls.mediaType, label, source: "network",
    }]);
    refreshBadge(details.tabId);
  },
  { urls: ["<all_urls>"] }
);

// DOM candidates from content.js; popup queries via GET_CANDIDATES.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "DOM_CANDIDATES" && sender.tab) {
    registry.addForTab(sender.tab.id, message.candidates);
    refreshBadge(sender.tab.id);
  } else if (message.type === "GET_CANDIDATES") {
    sendResponse({ candidates: registry.getForTab(message.tabId) });
    return true; // async response
  }
});

// Clear a tab's registry when it navigates or closes.
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "loading") {
    registry.clearTab(tabId);
    refreshBadge(tabId);
  }
});
chrome.tabs.onRemoved.addListener((tabId) => registry.clearTab(tabId));

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    chrome.storage.sync.set({ serverUrl: "http://localhost:8000" });
  }
});
```

Add `"lib/detect.js"` and `"lib/registry.js"` to the extension package via the manifest's `background` entry — confirm `manifest.json` `background` is `{"service_worker": "background.js"}` (importScripts loads the libs at runtime; no manifest change needed for Chrome). For `manifest.firefox.json`, if it uses `background.scripts`, list `["lib/detect.js", "lib/registry.js", "background.js"]` there instead.

- [ ] **Step 6: Run all extension tests**

Run: `cd browser-extension && bun test`
Expected: PASS (all suites: detect, dom-scan, registry).

- [ ] **Step 7: Commit**

```bash
git add browser-extension/lib/registry.js browser-extension/background.js browser-extension/tests/registry.test.js browser-extension/manifest.firefox.json
git commit -m "feat(ext): network sniffing + per-tab media registry in background worker

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3 — Popup capture client

### Task 7: Popup capture helpers (pure, tested)

**Files:**
- Create: `browser-extension/lib/capture-client.js`
- Create: `browser-extension/tests/capture-client.test.js`

**Interfaces:**
- Produces (global + `module.exports`ed):
  - `normalizeServerUrl(raw: string): string` — trims, drops trailing slash.
  - `deriveFilename(label: string, format: string): string` — safe filename, correct extension (e.g. `"Page — youtube.com"`, `"mp3"` → `"youtube.com.mp3"`; strips illegal chars; falls back to `"sift-capture.<ext>"`).
  - `buildCaptureBody(candidate, format, quality): object` — `{url, kind, format, quality}`.

- [ ] **Step 1: Write the failing test**

```javascript
// browser-extension/tests/capture-client.test.js
import { test, expect } from "bun:test";
const { normalizeServerUrl, deriveFilename, buildCaptureBody } = require("../lib/capture-client.js");

test("normalizeServerUrl drops trailing slash and trims", () => {
  expect(normalizeServerUrl("  http://localhost:8000/ ")).toBe("http://localhost:8000");
});

test("deriveFilename uses format extension and strips illegal chars", () => {
  expect(deriveFilename("Page — youtube.com", "mp3")).toBe("youtube.com.mp3");
});

test("deriveFilename falls back when label empty", () => {
  expect(deriveFilename("", "mp4")).toBe("sift-capture.mp4");
});

test("buildCaptureBody maps fields", () => {
  const c = { url: "https://x.com/v.mp4", kind: "file" };
  expect(buildCaptureBody(c, "mp3", "high")).toEqual({
    url: "https://x.com/v.mp4", kind: "file", format: "mp3", quality: "high",
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd browser-extension && bun test tests/capture-client.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the helpers**

Create `browser-extension/lib/capture-client.js`:

```javascript
function normalizeServerUrl(raw) {
  return String(raw || "").trim().replace(/\/+$/, "");
}

function deriveFilename(label, format) {
  const ext = format || "bin";
  let base = String(label || "").replace(/^Page —\s*/, "").replace(/^.*?—\s*/, "").trim();
  base = base.replace(/[^a-zA-Z0-9._-]+/g, "_").replace(/^_+|_+$/g, "");
  if (!base) base = "sift-capture";
  return `${base}.${ext}`;
}

function buildCaptureBody(candidate, format, quality) {
  return { url: candidate.url, kind: candidate.kind || "page", format, quality };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { normalizeServerUrl, deriveFilename, buildCaptureBody };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd browser-extension && bun test tests/capture-client.test.js`
Expected: PASS (4 pass).

- [ ] **Step 5: Commit**

```bash
git add browser-extension/lib/capture-client.js browser-extension/tests/capture-client.test.js
git commit -m "feat(ext): pure popup capture helpers (filename, body, server url)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Popup UI + convert/poll/download flow

**Files:**
- Rewrite: `browser-extension/popup.html`
- Rewrite: `browser-extension/popup.js`
- Modify: `browser-extension/README.md` (document new behavior, API key, permissions)

**Interfaces:**
- Consumes: `normalizeServerUrl`, `deriveFilename`, `buildCaptureBody` (Task 7); background `GET_CANDIDATES` message (Task 6); server `POST /api/capture`, `GET /api/download/{job_id}`, `GET /api/download/{job_id}/file` (Tasks 3 + existing).
- Produces: a working popup. No new exported interface.

- [ ] **Step 1: Rewrite `popup.html`**

Replace `browser-extension/popup.html` body content with controls (keep existing `<style>` conventions): a `#candidates` list container, a `#format` `<select>` (options `mp3`, `mp4`), a `#quality` `<select>` (options `low`/`medium`/`high`/`highest`, default `high`), a `#convert-btn` button, a `#progress` element, a `#message` element, and in the config footer a `#server-url` input plus a new `#api-key` input (type `password`) and `#save-btn`. Load the libs and popup script at the end of `<body>`:

```html
  <script src="lib/detect.js"></script>
  <script src="lib/capture-client.js"></script>
  <script src="popup.js"></script>
```

- [ ] **Step 2: Rewrite `popup.js`**

Replace `browser-extension/popup.js` with:

```javascript
const DEFAULT_SERVER = "http://localhost:8000";
let serverUrl = DEFAULT_SERVER;
let apiKey = "";
let candidates = [];
let selectedIndex = 0;

const els = {};
function $(id) { return document.getElementById(id); }

function authHeaders(extra) {
  const h = Object.assign({ "Content-Type": "application/json" }, extra || {});
  if (apiKey) h["X-API-Key"] = apiKey;
  return h;
}

function showMessage(text, isError) {
  els.message.textContent = text;
  els.message.className = `message ${isError ? "error" : "success"}`;
  els.message.style.display = "block";
}

function renderCandidates() {
  els.candidates.innerHTML = "";
  if (!candidates.length) {
    els.candidates.textContent = "No media detected on this page.";
    els.convertBtn.disabled = true;
    return;
  }
  els.convertBtn.disabled = false;
  candidates.forEach((c, i) => {
    const row = document.createElement("label");
    row.className = "candidate";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "candidate";
    radio.checked = i === selectedIndex;
    radio.addEventListener("change", () => { selectedIndex = i; });
    row.appendChild(radio);
    row.appendChild(document.createTextNode(" " + c.label));
    els.candidates.appendChild(row);
  });
}

async function loadCandidates() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.runtime.sendMessage({ type: "GET_CANDIDATES", tabId: tab.id }, (resp) => {
    candidates = (resp && resp.candidates) || [];
    selectedIndex = 0;
    renderCandidates();
  });
}

async function pollJob(jobId) {
  for (let i = 0; i < 600; i++) { // up to ~10 min at 1s
    const resp = await fetch(`${serverUrl}/api/download/${jobId}`, { headers: authHeaders() });
    if (!resp.ok) throw new Error(`Status check failed: ${resp.status}`);
    const job = await resp.json();
    els.progress.value = Math.round((job.progress || 0) * 100);
    if (job.status === "completed") return job;
    if (job.status === "failed") throw new Error(job.error || "Conversion failed");
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("Timed out waiting for conversion");
}

async function onConvert() {
  const candidate = candidates[selectedIndex];
  if (!candidate) return;
  const format = els.format.value;
  const quality = els.quality.value;
  els.convertBtn.disabled = true;
  els.progress.style.display = "block";
  els.progress.value = 0;
  try {
    const resp = await fetch(`${serverUrl}/api/capture`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(buildCaptureBody(candidate, format, quality)),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${resp.status}`);
    }
    const { job_id, download_url } = await resp.json();
    const job = await pollJob(job_id);
    const fileUrl = serverUrl + (job.download_url || download_url);
    chrome.downloads.download({
      url: fileUrl,
      filename: deriveFilename(candidate.label, format),
      headers: apiKey ? [{ name: "X-API-Key", value: apiKey }] : undefined,
    });
    showMessage("Saved to your Downloads folder!", false);
  } catch (e) {
    showMessage(e.message.includes("Failed to fetch")
      ? `Cannot connect to ${serverUrl}. Is Sift running?` : e.message, true);
  } finally {
    els.convertBtn.disabled = false;
  }
}

async function init() {
  ["candidates", "format", "quality", "convert-btn", "progress", "message",
   "server-url", "api-key", "save-btn"].forEach((id) => {
    els[id.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = $(id);
  });
  const stored = await chrome.storage.sync.get(["serverUrl", "apiKey"]);
  serverUrl = normalizeServerUrl(stored.serverUrl || DEFAULT_SERVER);
  apiKey = stored.apiKey || "";
  els.serverUrl.value = serverUrl;
  els.apiKey.value = apiKey;
  els.convertBtn.addEventListener("click", onConvert);
  els.saveBtn.addEventListener("click", async () => {
    serverUrl = normalizeServerUrl(els.serverUrl.value);
    apiKey = els.apiKey.value;
    await chrome.storage.sync.set({ serverUrl, apiKey });
    showMessage("Settings saved!", false);
  });
  await loadCandidates();
}

init();
```

- [ ] **Step 3: Update the README**

In `browser-extension/README.md`, update Usage and Supported Platforms: detection now works on **any** page (DOM + network sniffing), the popup lets you pick mp3/mp4 + quality and saves straight to your Downloads folder, and add a note about the new **API key** field and the broadened permissions (`<all_urls>`, `webRequest`, `downloads`) with the privacy rationale (media URLs only, in-memory, nothing sent until you click convert).

- [ ] **Step 4: Run all extension tests (no regressions)**

Run: `cd browser-extension && bun test`
Expected: PASS (all suites).

- [ ] **Step 5: Manual E2E verification**

Load the unpacked extension (`chrome://extensions` → Load unpacked → `browser-extension`). Start the server (`uv run uvicorn app.main:app --reload`). Verify on three pages:
1. A whitelisted platform (e.g. a YouTube watch page) → badge shows a count, popup lists a page candidate, convert to mp3 downloads a file.
2. A site with an embedded HTML5 `<video>` → DOM candidate appears.
3. A site streaming HLS (network `.m3u8`) → a stream candidate appears via sniffing; convert to mp4 downloads a file.

Record results in the commit message. If a step fails, debug before committing (use superpowers:systematic-debugging).

- [ ] **Step 6: Commit**

```bash
git add browser-extension/popup.html browser-extension/popup.js browser-extension/README.md
git commit -m "feat(ext): popup capture flow — detect, pick mp3/mp4, save to browser

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Docs & TODO sync

**Files:**
- Modify: `docs/todo.md` (P2 Browser Extension section)
- Modify: `README.md` (root — if it lists extension capabilities)

- [ ] **Step 1: Update `docs/todo.md`**

Under `## P2: Browser Extension`, check off the two open items and add a sub-section recording the universal-capture upgrade:

```markdown
- [x] Show notification/toast on successful queue
- [x] Optional: Show download progress in extension popup

### Universal Capture (2026-06-23) ✅
- [x] Detect media on any page (DOM scan + network sniffing)
- [x] In-popup format (mp3/mp4) + quality selection
- [x] `GenericDownloader` yt-dlp fallback + `POST /api/capture`
- [x] Save converted file straight to the browser (chrome.downloads)
- [x] API-key field in popup config
```

- [ ] **Step 2: Update root `README.md`** if it documents the extension or supported platforms (add: detection now works on any page, in-popup conversion to mp3/mp4). Skip if the root README doesn't mention the extension.

- [ ] **Step 3: Commit**

```bash
git add docs/todo.md README.md
git commit -m "docs: record universal-capture extension upgrade

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** §2 architecture → Tasks 1-8; §3 detection engine → Tasks 4-6; §4 popup UX → Tasks 7-8; §5 generic downloader + capture API → Tasks 2-3; §6 security/auth/privacy → SSRF in Task 3, API-key in Tasks 6-8, privacy rule in Global Constraints + Task 8 README; §7 phasing → the three phases; §8 testing → pytest (Tasks 1-3) + bun (Tasks 4-7) + manual E2E (Task 8). No gaps.
- **Placeholder scan:** every code step contains complete code; no TBD/TODO/"handle edge cases".
- **Type consistency:** candidate shape `{url, kind, mediaType, label, source}` consistent across `detect.js`, `dom-scan.js`, `registry.js`, popup; `classifyMediaUrl`/`mergeCandidates`/`dedupeKey`/`createRegistry`/`scanDomForMedia`/`buildCaptureBody`/`deriveFilename`/`normalizeServerUrl` names match between definition, consumers, and tests; `Platform.GENERIC` and `/api/download/{job_id}/file` consistent server-side.
