# AudioGrab Feature Roadmap

## Priority Matrix

| Feature | Difficulty | Impact | Priority |
|---------|------------|--------|----------|
| Metadata Tagging | Low | High | P0 ✅ |
| Speaker Diarization | High | Very High | P1 ✅ |
| Browser Extension | Medium | High | P2 ✅ |
| LLM Summarization | Medium | Medium | P3 ✅ |
| Watch Folders & Subscriptions | Medium | High | P4 ✅ |
| Audio Pre-processing | Medium | Medium | P5 ✅ |
| AI Provider Manager | Medium | High | P6 |
| Sentiment & Vibe Analysis | Medium | Medium | P7 |
| Social Media Clip Generator | High | High | P8 |
| AI Translation & Dubbing | Very High | Very High | P9 |

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

## P3: LLM-Powered Summarization ✅ COMPLETED

**Goal:** Generate summaries and chapters for long transcriptions.

### Tasks

- [x] Create summarization service (`app/core/summarizer.py`)
- [x] Support multiple LLM backends:
  - [x] Ollama (local, free)
  - [x] OpenAI API
  - [x] Anthropic API
  - [x] OpenAI-compatible endpoints (LM Studio, etc.)
- [x] Add API key configuration in settings
- [x] Summarization types:
  - [x] Bullet-point summary
  - [x] Chapter markers with timestamps
  - [x] Key topics/themes extraction
  - [x] Action items (for meeting-style content)
  - [x] Full comprehensive summary
- [x] Add "Summarize" button in Web UI transcription view
- [x] Chunking strategy for long transcripts (context window limits)
- [ ] Cache summaries in database
- [ ] Export summary alongside transcript

---

## P4: Watch Folders & Subscriptions ✅ COMPLETED

**Goal:** Automated archiving of RSS feeds and channels.

### Tasks

- [x] Create subscription model in database
- [x] Subscription types:
  - [x] RSS feed URL
  - [x] YouTube channel/playlist
  - [ ] X user's Spaces (if API allows)
- [x] Background worker for checking subscriptions:
  - [x] Configurable check interval (default: 1 hour)
  - [x] Track last checked timestamp
  - [x] Track downloaded episode IDs to avoid duplicates
- [x] Subscription management API endpoints:
  - [x] `POST /subscriptions` - Add subscription
  - [x] `GET /subscriptions` - List subscriptions
  - [x] `DELETE /subscriptions/{id}` - Remove subscription
  - [x] `POST /subscriptions/{id}/check` - Force check now
- [x] Web UI subscription management page
- [x] Auto-transcribe option per subscription
- [x] Download limit (e.g., keep last N episodes)
- [x] Notification on new downloads (webhook/email)

---

## P5: Audio Pre-processing (Voice Isolation) ✅ COMPLETED

**Goal:** Improve transcription accuracy for noisy recordings.

### Tasks

- [x] Research audio enhancement options:
  - [ ] DeepFilterNet (ML-based noise reduction)
  - [x] FFmpeg filters (high-pass, low-pass, noise gate)
  - [ ] Silero VAD for voice activity detection
- [x] Create audio enhancement service (`app/core/enhancer.py`)
- [x] Enhancement presets:
  - [x] Light (basic noise reduction)
  - [x] Medium (voice isolation)
  - [x] Heavy (aggressive filtering for very noisy audio)
- [x] Add "Enhance Audio" toggle in Web UI
- [x] Option to keep both original and enhanced versions
- [x] Apply enhancement before transcription (optional pipeline step)
- [x] Preview enhancement before full processing

---

## P6: AI Provider Manager (LiteLLM Integration)

**Goal:** Create an AI-agnostic gateway supporting multiple LLM providers through a unified interface.

### Tasks

- [ ] Add `litellm` dependency for universal LLM API translation
- [ ] Update `app/core/summarizer.py` to use LiteLLM:
  - [ ] Support OpenAI-compatible API format
  - [ ] Handle provider-specific authentication
- [ ] Supported AI backends:
  - [ ] **Ollama** (Local Llama 3) - Privacy-first, free, runs locally
  - [ ] **OpenAI** (GPT-4, GPT-4o) - High quality cloud option
  - [ ] **Anthropic** (Claude 3.5 Sonnet) - Best for long-form transcript reasoning
  - [ ] **Groq** (Cloud Llama 3) - Fast inference (500+ tokens/sec)
  - [ ] **DeepSeek** - Budget-friendly for high-volume summarization
  - [ ] **Custom OpenAI-compatible endpoints** (LM Studio, etc.)
- [ ] Create AI Settings management:
  - [ ] `POST /settings/ai` - Save AI provider configuration
  - [ ] `GET /settings/ai` - Get current AI settings
  - [ ] Store API keys securely in SQLite `settings` table
- [ ] Web UI Settings tab:
  - [ ] Provider dropdown (OpenAI, Ollama, Anthropic, Groq, Custom)
  - [ ] API key input field
  - [ ] Base URL field (for custom/local endpoints)
  - [ ] Model selection per provider
  - [ ] Test connection button
- [ ] Docker Compose setup for AudioGrab + Ollama together

---

## P7: Sentiment & Vibe Analysis

**Goal:** Generate emotional timeline showing the "emotional heat" of audio content.

### Tasks

- [ ] Create sentiment analysis service (`app/core/sentiment_analyzer.py`)
- [ ] Research and select sentiment analysis approach:
  - [ ] LLM-based sentiment prompts (most flexible)
  - [ ] FinBERT (financial sentiment, good for podcast discussions)
  - [ ] General sentiment models from HuggingFace
- [ ] Sentiment tagging types:
  - [ ] Positive/Negative/Neutral
  - [ ] Bullish/Bearish (for financial content)
  - [ ] Aggressive/Calm (for debates)
  - [ ] Excitement level (0-100)
- [ ] Analyze transcript segments:
  - [ ] Process each transcript segment individually
  - [ ] Aggregate scores over time windows
  - [ ] Identify "heated" moments and debates
- [ ] Web UI visualization:
  - [ ] Emotional timeline/heatmap alongside transcript
  - [ ] Color-coded segments (red=heated, green=positive, etc.)
  - [ ] Click on timeline to jump to that moment
  - [ ] Summary of overall emotional arc
- [ ] API endpoints:
  - [ ] `POST /jobs/{id}/analyze-sentiment` - Run sentiment analysis
  - [ ] `GET /jobs/{id}/sentiment` - Get sentiment results
- [ ] Export sentiment data with transcript

---

## P8: Social Media Clip Generator

**Goal:** Automatically identify viral-worthy moments and generate clips for social media.

### Tasks

- [ ] Create clip generator service (`app/core/clip_generator.py`)
- [ ] AI-powered clip identification:
  - [ ] Feed transcript to LLM with prompt for finding hook-worthy segments
  - [ ] Identify most controversial/insightful 15-60 second segments
  - [ ] Score clips by "viral potential"
  - [ ] Consider speaker energy/sentiment in selection
- [ ] Clip metadata generation:
  - [ ] Auto-generate catchy captions
  - [ ] Suggest relevant hashtags
  - [ ] Create hook text for the first 3 seconds
- [ ] Clip extraction:
  - [ ] Extract audio segment with FFmpeg
  - [ ] Generate timestamps for video editing
  - [ ] Support multiple aspect ratios (9:16 for TikTok/Reels, 1:1 for Instagram)
- [ ] Web UI "Generate Viral Clips" feature:
  - [ ] Button in transcription view
  - [ ] Preview suggested clips with timestamps
  - [ ] Edit/adjust clip boundaries
  - [ ] Download clips individually or as batch
  - [ ] Copy caption/hashtags to clipboard
- [ ] API endpoints:
  - [ ] `POST /jobs/{id}/generate-clips` - Generate clip suggestions
  - [ ] `GET /jobs/{id}/clips` - List generated clips
  - [ ] `POST /jobs/{id}/clips/{clip_id}/export` - Export specific clip
- [ ] Platform-specific formatting:
  - [ ] TikTok (9:16, max 3 min)
  - [ ] Instagram Reels (9:16, max 90 sec)
  - [ ] YouTube Shorts (9:16, max 60 sec)
  - [ ] Twitter/X (16:9, max 2:20)

---

## P9: AI Translation & Dubbing

**Goal:** Translate transcripts and re-voice content in different languages while preserving speaker characteristics.

### Tasks

- [ ] Create translation service (`app/core/translator.py`)
- [ ] Translation pipeline:
  - [ ] Use existing transcription as source
  - [ ] LLM-based translation (supports context and nuance)
  - [ ] Preserve speaker labels and timestamps
  - [ ] Handle technical terms and proper nouns
- [ ] Supported language pairs:
  - [ ] Chinese (小宇宙) → English
  - [ ] English → Spanish/French/German/Japanese
  - [ ] Auto-detect source language
- [ ] Text-to-Speech (TTS) integration:
  - [ ] Research TTS options:
    - [ ] Coqui TTS (open source)
    - [ ] OpenVoice (voice cloning)
    - [ ] ElevenLabs API (high quality)
    - [ ] Azure Speech Services
  - [ ] Voice cloning from original speaker
  - [ ] Maintain original pacing and timing
- [ ] Create dubbing service (`app/core/dubber.py`):
  - [ ] Sync translated speech with original timing
  - [ ] Handle speed adjustments for different language lengths
  - [ ] Mix dubbed audio with original background sounds (optional)
- [ ] Web UI translation features:
  - [ ] "Translate" button in transcription view
  - [ ] Language selector dropdown
  - [ ] Preview translated text before TTS
  - [ ] "Generate Dubbed Audio" button
  - [ ] Side-by-side original/translated view
- [ ] API endpoints:
  - [ ] `POST /jobs/{id}/translate` - Translate transcript
  - [ ] `GET /jobs/{id}/translation/{lang}` - Get translation
  - [ ] `POST /jobs/{id}/dub` - Generate dubbed audio
- [ ] Export options:
  - [ ] Translated transcript (TXT, SRT, VTT)
  - [ ] Dubbed audio file
  - [ ] Bilingual subtitle file

---

## Future Ideas (Backlog)

- [x] Batch download from URL list/file ✅
- [x] Download queue priority levels ✅
- [x] Scheduled downloads (download at specific time) ✅
- [ ] Storage management (auto-cleanup old files)
- [ ] Multi-language UI
- [ ] Mobile-responsive Web UI improvements
- [ ] Docker Compose with GPU support for transcription
- [x] Webhook notifications for job completion ✅
- [ ] Export to cloud storage (S3, Google Drive, Dropbox)
- [x] Collaborative annotations on transcripts ✅
- [ ] Real-time transcription (live audio streams)
- [ ] Podcast RSS feed generation from downloaded content
- [ ] Audio fingerprinting for duplicate detection
- [ ] Integration with note-taking apps (Notion, Obsidian)
- [ ] Voice search within transcripts
