# AudioGrab Feature Roadmap

## Priority Matrix

| Feature | Difficulty | Impact | Priority |
|---------|------------|--------|----------|
| Metadata Tagging | Low | High | P0 |
| Speaker Diarization | High | Very High | P1 |
| Browser Extension | Medium | High | P2 |
| LLM Summarization | Medium | Medium | P3 |
| Watch Folders & Subscriptions | Medium | High | P4 |
| Audio Pre-processing | Medium | Medium | P5 |

---

## P0: Smart Metadata & Tagging ✅ COMPLETED

**Goal:** Automatically fetch and embed ID3 tags (Title, Artist, Album Art, Year) for all platforms.

### Tasks

- [x] Add `mutagen` dependency for ID3 tag manipulation
- [x] Create metadata service (`app/core/metadata_tagger.py`)
- [x] Platform-specific metadata extractors:
  - [x] X Spaces: Scrape Space title, Host handle as "Artist"
  - [x] YouTube: Extract title, channel name, thumbnail
  - [x] Apple Podcasts: Pull from RSS feed (title, description, artwork)
  - [x] Spotify: Use spotDL metadata (already has some)
  - [x] 小宇宙: Extract episode metadata from API
- [x] Embed metadata into downloaded files:
  - [x] Title
  - [x] Artist/Author
  - [x] Album (show name for podcasts)
  - [x] Album Art (thumbnail/cover)
  - [x] Year/Date
  - [x] Description in "Comments" tag
- [ ] Add option to customize filename template (e.g., `{artist} - {title}`)
- [x] Add `embed_metadata` option in API (default: true)

---

## P1: Speaker Diarization (Who Spoke When) ✅ COMPLETED

**Goal:** Identify different speakers in transcriptions, especially for X Spaces and Podcasts.

See [diarization-setup.md](./diarization-setup.md) for setup instructions.

### Tasks

- [x] Research and select diarization library:
  - [x] Selected: `pyannote-audio` (most accurate, requires HuggingFace token)
- [x] Add optional dependency group `[diarize]`
- [x] Create diarization service (`app/core/diarizer.py`)
- [x] Integrate with existing transcription pipeline:
  - [x] Run diarization after transcription
  - [x] Merge speaker labels with transcript segments
- [x] Update output formats:
  - [x] Plain text with speaker labels (`dialogue` format)
  - [x] SRT with speaker prefixes
  - [x] JSON with speaker IDs per segment
- [x] Add Web UI toggle for diarization
- [x] Handle speaker renaming (Speaker 0 → "Host", etc.)
- [x] Add speaker count option (`num_speakers` parameter)

---

## P2: Browser Extension ✅ COMPLETED

**Goal:** One-click download from browser to AudioGrab Web UI.

### Tasks

- [x] Create Chrome extension manifest v3
- [x] Create Firefox extension manifest
- [x] Extension features:
  - [x] Detect supported URLs (X Spaces, YouTube, etc.)
  - [x] Show AudioGrab icon when on supported page
  - [x] Click to send URL to AudioGrab API
  - [x] Configuration page for AudioGrab server URL
- [x] Create simple bookmarklet alternative:
  ```javascript
  javascript:(function(){var s='http://localhost:8000';window.open(s+'/api/add?url='+encodeURIComponent(window.location.href)+'&action=transcribe')})()
  ```
- [x] Add `/add` endpoint to API for browser integration
- [ ] Show notification/toast on successful queue
- [ ] Optional: Show download progress in extension popup

---

## P3: LLM-Powered Summarization

**Goal:** Generate summaries and chapters for long transcriptions.

### Tasks

- [ ] Create summarization service (`services/summarization.py`)
- [ ] Support multiple LLM backends:
  - [ ] Ollama (local, free)
  - [ ] OpenAI API
  - [ ] Anthropic API
  - [ ] OpenAI-compatible endpoints (LM Studio, etc.)
- [ ] Add API key configuration in settings
- [ ] Summarization types:
  - [ ] Bullet-point summary
  - [ ] Chapter markers with timestamps
  - [ ] Key topics/themes extraction
  - [ ] Action items (for meeting-style content)
- [ ] Add "Summarize" button in Web UI transcription view
- [ ] Chunking strategy for long transcripts (context window limits)
- [ ] Cache summaries in database
- [ ] Export summary alongside transcript

---

## P4: Watch Folders & Subscriptions

**Goal:** Automated archiving of RSS feeds and channels.

### Tasks

- [ ] Create subscription model in database
- [ ] Subscription types:
  - [ ] RSS feed URL
  - [ ] YouTube channel/playlist
  - [ ] X user's Spaces (if API allows)
- [ ] Background worker for checking subscriptions:
  - [ ] Configurable check interval (default: 1 hour)
  - [ ] Track last checked timestamp
  - [ ] Track downloaded episode IDs to avoid duplicates
- [ ] Subscription management API endpoints:
  - [ ] `POST /subscriptions` - Add subscription
  - [ ] `GET /subscriptions` - List subscriptions
  - [ ] `DELETE /subscriptions/{id}` - Remove subscription
  - [ ] `POST /subscriptions/{id}/check` - Force check now
- [ ] Web UI subscription management page
- [ ] Auto-transcribe option per subscription
- [ ] Download limit (e.g., keep last N episodes)
- [ ] Notification on new downloads (webhook/email)

---

## P5: Audio Pre-processing (Voice Isolation)

**Goal:** Improve transcription accuracy for noisy recordings.

### Tasks

- [ ] Research audio enhancement options:
  - [ ] DeepFilterNet (ML-based noise reduction)
  - [ ] FFmpeg filters (high-pass, low-pass, noise gate)
  - [ ] Silero VAD for voice activity detection
- [ ] Create audio enhancement service (`services/audio_enhance.py`)
- [ ] Enhancement presets:
  - [ ] Light (basic noise reduction)
  - [ ] Medium (voice isolation)
  - [ ] Heavy (aggressive filtering for very noisy audio)
- [ ] Add "Enhance Audio" toggle in Web UI
- [ ] Option to keep both original and enhanced versions
- [ ] Apply enhancement before transcription (optional pipeline step)
- [ ] Preview enhancement before full processing

---

## Future Ideas (Backlog)

- [ ] Batch download from URL list/file
- [ ] Download queue priority levels
- [ ] Scheduled downloads (download at specific time)
- [ ] Storage management (auto-cleanup old files)
- [ ] Multi-language UI
- [ ] Mobile-responsive Web UI improvements
- [ ] Docker Compose with GPU support for transcription
- [ ] Webhook notifications for job completion
- [ ] Export to cloud storage (S3, Google Drive, Dropbox)
- [ ] Collaborative annotations on transcripts
