# Test Links

Sample URLs for checking each platform's download path by hand.

Probe metadata only (fast, no bytes downloaded) through the adapters themselves:

```bash
uv run python -c "
import asyncio; from app.core import get_metadata
print(asyncio.run(get_metadata('<URL>')))"
```

Or exercise the full path over the API:

```bash
curl -s -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url":"<URL>","platform":"auto","quality":"high"}'
```

Then poll `GET /api/download/{job_id}` until `status` is `completed` / `failed`.

## Verified samples

Last run **2026-08-24** against yt-dlp **2026.08.19** — all six returned metadata.

| Platform | Test URL | Notes |
|----------|----------|-------|
| YouTube (audio) | `https://www.youtube.com/watch?v=I-PMiyYZkrs` | Needs a JS runtime (`deno`) for the `n` challenge; without one yt-dlp warns and may drop formats |
| X / Twitter video | `https://x.com/SpaceX/status/2072695632104468543?s=20` | Public post. Auth is used when configured and retried without it if the session has expired |
| Apple Podcasts | `https://podcasts.apple.com/de/podcast/351-rache-ist-kein-sch%C3%B6nes-ferd-sommerhack/id1292709842?i=1000774914977` | Large (~100 MB). Cover-art transcode handled via ffmpeg `-vn` |
| 小宇宙 (Xiaoyuzhou) | `https://www.xiaoyuzhoufm.com/episode/6a4123349d2f5743683f2bd6` | Scrapes `__NEXT_DATA__` for the audio URL |
| 喜马拉雅 (Ximalaya) | `https://www.ximalaya.com/sound/998052123` | Single `/sound/` episodes only; album pages unsupported. Paid/VIP episodes can't be downloaded |
| Instagram Reel | `https://www.instagram.com/reel/DZKus9XB34d/` | Requires login cookies — set `INSTAGRAM_COOKIES_FILE`. See [instagram-setup.md](instagram-setup.md) |

## Platforms that cannot have a fixed sample

These are supported, but no URL stays valid long enough to check in. Grab a
fresh one when testing.

| Platform | Why | How to get one |
|----------|-----|----------------|
| 小红书 (RedNote) | Post URLs carry a short-lived `xsec_token` query parameter; a saved link stops resolving once it expires | Open a post on xiaohongshu.com and copy the full URL from the address bar, `xsec_token` and all |
| Discord | Attachment CDN links are signed and time-limited | Copy a fresh attachment link from a Discord message |
| X Spaces | Recordings are removed roughly 30 days after the Space ends | Take a Space that is live or recently recorded |
| Spotify | Requires an `sp_dc` session cookie, and availability is account- and region-dependent | Any episode URL from your own logged-in account |

A verification run therefore covers **six** of the ten supported platforms
without manual setup. The other four need a fresh URL each time — an empty
result from one of them is far more likely to be an expired link than a broken
adapter, so confirm the URL works in a browser before filing a bug.

## Requirements recap

- **YouTube:** a JavaScript runtime (`deno`) so yt-dlp can solve the `n` challenge.
- **Instagram:** authenticated cookies (`INSTAGRAM_COOKIES_FILE` → an exported Netscape cookies.txt).
  Non-coder walkthrough: [instagram-setup.md](instagram-setup.md).
- **X / Twitter:** `TWITTER_AUTH_TOKEN` / `TWITTER_CT0` in `.env` for auth-gated posts. Public clips
  work without it, and an expired session falls back to an anonymous request rather than failing.
- **喜马拉雅 / Ximalaya:** single-episode `/sound/<id>` links only. Album pages
  (`ximalaya.com/<category>/<album_id>/`) return a clear "use a single episode link" message.
- **yt-dlp:** adapters run the version pinned in `pyproject.toml` (installed by `uv sync`) in
  preference to a system-wide install. Override with `YT_DLP_PATH`.
