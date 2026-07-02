# Universal Capture Browser Extension — Design

**Date:** 2026-06-23
**Status:** Approved (design), pending implementation plan
**Topic:** Turn the Sift browser extension into the primary capture surface — auto-detect media on any page (DOM + network sniffing), pick mp3/mp4 + quality in the popup, and save the converted file straight to the browser's Downloads folder.

> **Update (2026-07-02):** The extension is now built with the **[WXT](https://wxt.dev)** framework (TypeScript + Vite), replacing the original build-step-free plain-JS approach. The architecture, detection model, privacy rules, and phasing below are unchanged; only the delivery mechanics change — WXT entrypoints (`entrypoints/{background,content}.ts`, `entrypoints/popup/`), a shared `utils/` module for detection/pattern logic, a generated cross-browser manifest via `wxt.config.ts`, and Vitest instead of `bun test`. See the implementation plan's "Framework switched to WXT" note for the path remapping.

---

## 1. Problem & Goal

Today the extension only badge-detects a fixed whitelist of platforms, requires a click, ignores output format, and bounces the user to the web UI. The `/api/add` endpoint hardcodes transcription/download defaults and rejects any URL the `DownloaderFactory` doesn't recognize.

**Goal:** The user lands on *any* page with audio/video, opens the popup, sees the detected media, picks **mp3** or **mp4** (+ quality), clicks once, and the converted file downloads to their computer — no pasting, no whitelist limitation, no web-UI bounce.

**Approach (chosen):** Server does the heavy lifting (yt-dlp + ffmpeg + metadata pipeline). The extension is a smart detector + thin client. Rejected alternatives: in-browser ffmpeg.wasm (too heavy, unreliable for HLS, loses the server pipeline) and a hybrid direct-save path (two code paths for marginal gain).

---

## 2. Architecture

```
┌─ Browser ──────────────────────────────────────────────┐
│  content.js (per page)        background.js (SW)        │
│  • scan <video>/<audio>/      • webRequest listener:    │
│    <source>/og:* + page URL     capture .m3u8/.mp4/     │
│         │                       .mp3/.m4a responses     │
│         └──────────┬────────►  • per-tab media registry │
│                    │            • badge = #found        │
│  popup.js ◄────────┘                                    │
│  • list detected media for active tab                   │
│  • pick format (mp3/mp4) + quality                      │
│  • POST job → poll status → chrome.downloads.download() │
└──────────────────────────│──────────────────────────────┘
                           │ HTTP (+ X-API-Key)
┌─ Sift server ────────────▼──────────────────────────────┐
│  POST /api/capture   (new, format+quality aware)         │
│    → DownloaderFactory: known platform OR GenericDownloader│
│    → yt-dlp (generic extractor / direct stream / HLS)    │
│    → ffmpeg convert to mp3|mp4 → metadata tag            │
│  GET /api/download/{id}/file  (existing; serves file)    │
│  (SSRF allowlist validates every sniffed URL + redirect) │
└──────────────────────────────────────────────────────────┘
```

### Component boundaries (each independently testable)

1. **Detection engine** (extension) — input: page DOM + network events; output: a deduped per-tab list of candidates `{url, kind: "page"|"stream"|"file", mediaType, label, source}`. Knows nothing about the server.
2. **Capture client** (extension popup) — input: a chosen candidate + format + quality; output: a saved file. Owns server calls, progress polling, and `chrome.downloads`.
3. **Generic downloader** (server) — input: a URL (page/stream) + format + quality; output: a converted, metadata-tagged file. A new `PlatformDownloader` subclass registered as the lowest-priority factory fallback.
4. **Capture API** (server) — `POST /api/capture`; thin HTTP layer over the existing download-job machinery, extended to carry format/quality and route to the generic downloader when no specific platform matches.

---

## 3. Detection engine (extension)

**`content.js`** (runs on `<all_urls>`, `document_idle` + re-scan on SPA URL change and on a MutationObserver debounce):
- Collect from the DOM:
  - `<video>` / `<audio>` `src` and nested `<source src>`
  - `og:video`, `og:video:url`, `og:audio`, `twitter:player:stream` meta tags
  - The page URL itself (always added as a `kind:"page"` candidate — lets the server's yt-dlp try its extractors)
- Each candidate is normalized to `{url, kind, mediaType, label, source:"dom"}` and posted to the background worker.

**`background.js`** (MV3 service worker):
- `chrome.webRequest.onBeforeRequest` / `onResponseStarted` (observe-only; no blocking) filtered to media: URLs ending in or content-typed as `.m3u8`, `.mpd`, `.mp4`, `.m4a`, `.mp3`, `.aac`, `.webm`, `.ts`. For HLS, prefer the master/variant `.m3u8` and ignore individual `.ts` segments (collapse to their playlist when derivable).
- Maintain a **per-tab media registry** (`Map<tabId, Map<dedupeKey, candidate>>`), merging DOM candidates (from content.js) and network candidates. Dedupe by normalized URL.
- Update the action badge with the candidate count; clear on tab navigation/close.
- Respond to popup `GET_CANDIDATES` messages with the active tab's list.

**Notes:**
- Sniffing is observation-only; nothing is sent anywhere until the user clicks convert.
- Registry is in-memory per session (no persistence of browsing data). This is a deliberate privacy choice (see §6).

---

## 4. Capture client / popup UX (extension)

`popup.html` / `popup.js`:
- On open: query active tab → `GET_CANDIDATES` from background → render a list. Each row: a human label (e.g. "Page video — youtube.com", "HLS stream (.m3u8)", "Direct file (.mp4)"), the `kind`, and a select affordance.
- **Format selector:** mp3 / mp4. **Quality selector:** maps to the server's existing `QualityPreset` enum.
- Empty state: "No media detected on this page." (page URL candidate means this is rare).
- **Convert flow:**
  1. `POST /api/capture` with `{url, kind, format, quality}` + `X-API-Key` header → `{job_id}`.
  2. Poll `GET /api/download/{job_id}` until `completed` / `failed`, showing a progress bar (reuse `job.progress`).
  3. On completion: trigger `chrome.downloads.download({ url: serverUrl + job.download_url, headers: [{name:"X-API-Key", value:apiKey}], filename })`.
- **Config:** existing server-URL field + **new API-key field**, both stored in `chrome.storage.sync`.
- Errors surfaced inline (connection refused, unsupported, conversion failure), reusing the current `showMessage` pattern.

**Manifest (generated by WXT from `wxt.config.ts` — one config, both browsers):**
- `permissions`: add `webRequest`, `downloads`. Keep `activeTab`, `storage`.
- `host_permissions`: `<all_urls>` (required for sniffing + content script everywhere). The user's Sift server origin is requested via **`optional_host_permissions`** and granted at runtime when they save a non-default server URL (fixes the current hardcoded-localhost limitation).
- content script `matches`: `<all_urls>` (declared in `entrypoints/content.ts` via `defineContentScript`).

---

## 5. Server: generic downloader + capture API

**`GenericDownloader(PlatformDownloader)`** (new, `app/core/platforms/generic.py`):
- `PLATFORM = Platform.GENERIC` (new enum member).
- `can_handle_url()` → `True` for any `http(s)` URL. Registered **last** in `_get_platform_downloaders()` so specific platforms always win; it is the fallback only.
- `download()`:
  - For `kind:"page"` → invoke yt-dlp with its generic/auto extractor.
  - For `kind:"stream"` (`.m3u8`/`.mpd`) → yt-dlp handles HLS/DASH natively.
  - For `kind:"file"` (direct `.mp4`/`.mp3`) → yt-dlp direct fetch.
  - Then convert to requested `output_format` (mp3/mp4) via the existing ffmpeg path and run the existing metadata tagger.
- Follows the existing platform downloader contract (same `download()` signature, `output_format`, `quality`).

**`POST /api/capture`** (new, in `routes.py` or a small `capture_routes.py`, behind `verify_api_key`):
- Body: `{ url: str, kind: "page"|"stream"|"file" = "page", format: OutputFormat = mp3, quality: QualityPreset = <default> }`.
- Runs the sniffed/selected URL through the **existing SSRF allowlist validator** (re-checked on every redirect hop) before any fetch.
- `DownloaderFactory.detect_platform(url)`; if a specific platform matches, use it; otherwise use `GenericDownloader`.
- Creates a `DownloadJob` and runs `_process_download` with the requested format/quality (the existing POST `/download` machinery already threads `format`/`quality` through — this endpoint just makes them reachable for the extension and adds the generic fallback).
- Returns `{job_id, status, platform}`.
- `GET /api/download/{job_id}` (status) and `GET /api/download/{job_id}/file` (file) are reused as-is.

**Why a new endpoint instead of extending `/api/add`:** `/api/add` is a GET bookmarklet shortcut with transcribe/download semantics and hardcoded defaults; keeping it untouched avoids breaking existing bookmarklets. `/api/capture` is POST, format-aware, and generic-capable.

---

## 6. Security, permissions & privacy

- **SSRF:** every URL reaching `/api/capture` (especially sniffed stream URLs, which are page-supplied) goes through the existing allowlist validator with per-redirect re-checks. Internal/metadata IPs stay blocked.
- **Auth:** `/api/capture` and the file endpoint require `X-API-Key` when `API_KEY` is configured. The popup gains an API-key field; `chrome.downloads.download` sends the key via its `headers` option. (Fallback if a browser restricts that header: a short-lived signed query token on the file URL — noted, not built unless needed.)
- **Privacy (the cost of network sniffing):** broad host permissions let the worker observe all requests. Mitigations, stated as hard rules: (1) only media-typed URLs are ever stored; (2) the registry is in-memory, per-tab, never persisted; (3) nothing leaves the browser until the user explicitly clicks convert, and only the chosen URL + format are sent — never browsing history or page content. The store listing must disclose sniffing.
- **Store review:** `<all_urls>` + `webRequest` raises Chrome Web Store scrutiny. Justification (download manager) is legitimate; disclosure copy lives in the README/store description.

---

## 7. Phasing

Interdependent, so one spec — but built and verifiable in order:

- **Phase 1 — Server foundation.** `Platform.GENERIC`, `GenericDownloader`, `POST /api/capture` with SSRF + auth, format/quality wired through, generic fallback in the factory. Verifiable via API tests (curl a YouTube URL, a raw `.m3u8`, a direct `.mp4`; assert mp3 and mp4 outputs).
- **Phase 2 — Detection engine.** content.js DOM scan + background.js webRequest sniffing + per-tab registry + badge count. Verifiable by loading unpacked and inspecting the registry / badge across a whitelisted site, an embedded-player site, and a raw-stream page.
- **Phase 3 — Popup capture client.** Candidate list UI, format/quality pickers, API-key field, convert → poll → `chrome.downloads` save. End-to-end manual verification + the unit-testable pure functions (candidate normalization, dedupe, filename derivation).

---

## 8. Testing strategy

- **Server (pytest, in `tests/`):**
  - `GenericDownloader.can_handle_url` is the last-resort matcher; specific platforms still win.
  - `POST /api/capture`: known platform routes to its downloader; unknown URL routes to generic; format mp3/mp4 honored; SSRF-blocked URL → rejected; missing/invalid API key → 401/403 when `API_KEY` set.
  - Generic download integration test gated behind a network marker (yt-dlp against a stable public URL), or mocked yt-dlp for unit level.
- **Extension (pure-function unit tests, colocated `*.test.ts`, runnable with `bunx vitest`):**
  - Candidate normalization + dedupe (DOM + network merge).
  - HLS `.ts` → master `.m3u8` collapse.
  - Filename derivation from label/format.
- **Manual E2E checklist** for the three Phase-2/3 site categories above.

---

## 9. Out of scope (YAGNI)

- In-browser conversion (ffmpeg.wasm).
- DRM circumvention.
- Auto-download without a click.
- Per-download "save to Sift library vs computer" toggle (chosen: always save to browser).
- Transcription-from-popup (the server pipeline still offers it via the web UI; can be a later add).
