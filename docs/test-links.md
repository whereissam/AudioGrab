# Test Links

Reusable sample URLs for manually testing each platform's download path.
Submit with:

```bash
curl -s -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url":"<URL>","platform":"auto","quality":"high"}'
```

Then poll `GET /api/download/{job_id}` until `status` is `completed` / `failed`.

| Platform | Status | Test URL | Notes |
|----------|--------|----------|-------|
| YouTube (audio) | ✅ works | `https://www.youtube.com/watch?v=I-PMiyYZkrs` | Needs EJS n-challenge solver (auto via `--remote-components ejs:github` + local `deno`) |
| X / Twitter video | ✅ works | `https://x.com/SpaceX/status/2072695632104468543?s=20` | Public post; auth cookies auto-used for protected/sensitive posts |
| Apple Podcasts | ✅ works | `https://podcasts.apple.com/de/podcast/351-rache-ist-kein-sch%C3%B6nes-ferd-sommerhack/id1292709842?i=1000774914977` | Large (~100 MB). Cover-art transcode fixed via ffmpeg `-vn` |
| 小红书 (RedNote) | ✅ works | `https://www.xiaohongshu.com/explore/6a2417ff0000000006031044?xsec_token=...&xsec_source=pc_feed` | Fixed: removed custom UA/Referer that broke the extractor |
| 小宇宙 (Xiaoyuzhou) | ✅ works | `https://www.xiaoyuzhoufm.com/episode/6a4123349d2f5743683f2bd6` | Scrapes `__NEXT_DATA__` for the audio URL |
| 喜马拉雅 (Ximalaya) | ✅ works (single episode) | `https://www.ximalaya.com/sound/998052123` | Only single `/sound/` episodes; album/series pages unsupported (broken upstream extractor). Paid/VIP episodes can't be downloaded |
| Instagram Reel | ✅ works with cookies | `https://www.instagram.com/reel/DZKus9XB34d/` | Requires login — set `INSTAGRAM_COOKIES_FILE`. See [instagram-setup.md](instagram-setup.md) |

## Requirements recap

- **YouTube:** a JavaScript runtime (`deno`) so yt-dlp can solve the `n` challenge.
- **Instagram:** authenticated cookies (`INSTAGRAM_COOKIES_FILE` → an exported Netscape cookies.txt).
  Non-coder walkthrough: [instagram-setup.md](instagram-setup.md).
- **X / Twitter:** `TWITTER_AUTH_TOKEN` / `TWITTER_CT0` in `.env` for auth-gated posts (public clips work without).
- **喜马拉雅 / Ximalaya:** single-episode `/sound/<id>` links only. Album pages (`ximalaya.com/<category>/<album_id>/`)
  return a clear "use a single episode link" message rather than downloading.
