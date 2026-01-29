import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useState } from 'react'
import { Download, Loader2, AlertCircle, ArrowLeft, Mic, FileAudio, FileVideo, FileText, Twitter, Podcast, Music, Youtube, Radio, Video, Copy, Check } from 'lucide-react'

type DownloadStatus = 'idle' | 'loading' | 'success' | 'error'
type Platform = 'x_spaces' | 'apple_podcasts' | 'spotify' | 'youtube' | 'xiaoyuzhou' | 'x_video' | 'youtube_video'
type MediaType = 'audio' | 'video' | 'transcribe'
type WhisperModel = 'tiny' | 'base' | 'small' | 'medium' | 'large-v3' | 'turbo'
type TranscriptionFormat = 'text' | 'srt' | 'vtt' | 'json'

interface ContentInfo {
  title: string
  creator_name?: string
  creator_username?: string
  duration_seconds?: number
  file_size_mb?: number
  show_name?: string
  platform?: Platform
}

const AUDIO_PLATFORMS: Platform[] = ['x_spaces', 'apple_podcasts', 'spotify', 'youtube', 'xiaoyuzhou']
const VIDEO_PLATFORMS: Platform[] = ['x_video', 'youtube_video']

const PLATFORM_FORMATS: Record<Platform, { value: string; label: string; desc: string }[]> = {
  x_spaces: [
    { value: 'm4a', label: 'M4A', desc: 'Original quality' },
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
  ],
  apple_podcasts: [
    { value: 'm4a', label: 'M4A', desc: 'Original quality' },
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
  ],
  spotify: [
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
    { value: 'm4a', label: 'M4A', desc: 'AAC format' },
  ],
  youtube: [
    { value: 'm4a', label: 'M4A', desc: 'Best quality' },
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
  ],
  xiaoyuzhou: [
    { value: 'm4a', label: 'M4A', desc: 'Original quality' },
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
  ],
  x_video: [
    { value: 'mp4', label: 'MP4', desc: 'Best quality' },
  ],
  youtube_video: [
    { value: 'mp4', label: 'MP4', desc: 'Best quality' },
  ],
}

const PLATFORM_PLACEHOLDERS: Record<Platform, string> = {
  x_spaces: 'https://x.com/i/spaces/1vOxwdyYrlqKB',
  apple_podcasts: 'https://podcasts.apple.com/us/podcast/show-name/id123456789',
  spotify: 'https://open.spotify.com/episode/abc123',
  youtube: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
  xiaoyuzhou: 'https://www.xiaoyuzhoufm.com/episode/abc123',
  x_video: 'https://x.com/user/status/123456789',
  youtube_video: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
}

const PLATFORM_LABELS: Record<Platform, string> = {
  x_spaces: 'X Spaces',
  apple_podcasts: 'Apple Podcasts',
  spotify: 'Spotify',
  youtube: 'YouTube',
  xiaoyuzhou: '小宇宙',
  x_video: 'X/Twitter',
  youtube_video: 'YouTube',
}

const QUALITY_OPTIONS = [
  { value: 'medium', label: '480p' },
  { value: 'high', label: '720p' },
  { value: 'highest', label: '1080p' },
]

const WHISPER_MODELS: { value: WhisperModel; label: string; desc: string }[] = [
  { value: 'tiny', label: 'Tiny', desc: 'Fastest' },
  { value: 'base', label: 'Base', desc: 'Balanced' },
  { value: 'small', label: 'Small', desc: 'Better' },
  { value: 'medium', label: 'Medium', desc: 'High quality' },
  { value: 'large-v3', label: 'Large', desc: 'Best quality' },
  { value: 'turbo', label: 'Turbo', desc: 'Fast + accurate' },
]

const TRANSCRIPTION_FORMATS: { value: TranscriptionFormat; label: string; desc: string }[] = [
  { value: 'text', label: 'Text', desc: 'Plain text' },
  { value: 'srt', label: 'SRT', desc: 'Subtitles' },
  { value: 'vtt', label: 'VTT', desc: 'Web subtitles' },
  { value: 'json', label: 'JSON', desc: 'With timestamps' },
]

interface TranscriptionResult {
  text: string
  language: string
  language_probability: number
  duration_seconds: number
  formatted_output: string
  output_format: TranscriptionFormat
}

export const Route = createFileRoute('/')({
  component: AudioGrabHome,
})

function formatDuration(seconds: number): string {
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function AudioGrabHome() {
  const [mediaType, setMediaType] = useState<MediaType>('audio')
  const [platform, setPlatform] = useState<Platform>('x_spaces')
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<string>('m4a')
  const [quality, setQuality] = useState<string>('high')
  const [status, setStatus] = useState<DownloadStatus>('idle')
  const [message, setMessage] = useState('')
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [contentInfo, setContentInfo] = useState<ContentInfo | null>(null)

  // Transcription state
  const [whisperModel, setWhisperModel] = useState<WhisperModel>('base')
  const [transcriptionFormat, setTranscriptionFormat] = useState<TranscriptionFormat>('text')
  const [transcriptionResult, setTranscriptionResult] = useState<TranscriptionResult | null>(null)
  const [copied, setCopied] = useState(false)

  const handleMediaTypeChange = (newType: string) => {
    setMediaType(newType as MediaType)
    if (newType === 'audio') {
      setPlatform('x_spaces')
      setFormat('m4a')
    } else if (newType === 'video') {
      setPlatform('x_video')
      setFormat('mp4')
    }
    setUrl('')
    setStatus('idle')
    setMessage('')
    setTranscriptionResult(null)
  }

  const handlePlatformChange = (newPlatform: string) => {
    setPlatform(newPlatform as Platform)
    setUrl('')
    setFormat(PLATFORM_FORMATS[newPlatform as Platform][0].value)
    setStatus('idle')
    setMessage('')
  }

  const handleDownload = async () => {
    if (!url.trim()) {
      setStatus('error')
      setMessage('Please enter a valid URL')
      return
    }

    setStatus('loading')
    setMessage(`Downloading from ${PLATFORM_LABELS[platform]}...`)
    setDownloadUrl(null)
    setContentInfo(null)

    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, format, platform, quality }),
      })

      if (!response.ok) {
        const text = await response.text()
        let errorMsg = 'Download failed'
        try {
          const data = JSON.parse(text)
          if (Array.isArray(data.detail)) {
            errorMsg = data.detail.map((e: { msg?: string; loc?: string[] }) =>
              e.msg || JSON.stringify(e)
            ).join(', ')
          } else if (typeof data.detail === 'string') {
            errorMsg = data.detail
          } else if (data.detail) {
            errorMsg = JSON.stringify(data.detail)
          }
        } catch {
          errorMsg = text || errorMsg
        }
        throw new Error(errorMsg)
      }

      const data = await response.json()

      // Poll for job completion
      const jobId = data.job_id
      let attempts = 0
      const maxAttempts = 600 // 10 minutes for video downloads

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000))

        const statusResponse = await fetch(`/api/download/${jobId}`)
        const statusData = await statusResponse.json()

        if (statusData.status === 'completed') {
          setStatus('success')
          setMessage('Download complete!')
          setDownloadUrl(`/api/download/${jobId}/file`)

          const info = statusData.content_info || statusData.space_info
          if (info) {
            setContentInfo({
              title: info.title || 'Unknown',
              creator_name: info.creator_name || info.host_display_name,
              creator_username: info.creator_username || info.host_username,
              duration_seconds: info.duration_seconds,
              file_size_mb: statusData.file_size_mb,
              show_name: info.show_name,
              platform: statusData.platform,
            })
          } else {
            setContentInfo({
              title: 'Downloaded Media',
              file_size_mb: statusData.file_size_mb,
              platform: statusData.platform,
            })
          }
          return
        } else if (statusData.status === 'failed') {
          let errorMsg = 'Download failed'
          if (typeof statusData.error === 'string') {
            errorMsg = statusData.error
          } else if (statusData.error && typeof statusData.error === 'object') {
            errorMsg = statusData.error.message || statusData.error.detail || JSON.stringify(statusData.error)
          }
          throw new Error(errorMsg)
        }

        if (attempts % 10 === 0) {
          const progress = Math.min(Math.floor(attempts / 6), 95)
          setMessage(`Downloading from ${PLATFORM_LABELS[platform]}... ${progress}%`)
        }

        attempts++
      }

      throw new Error('Download timed out')
    } catch (error) {
      setStatus('error')
      if (error instanceof TypeError && error.message.includes('fetch')) {
        setMessage('Cannot connect to server. Make sure the backend is running.')
      } else if (error instanceof Error) {
        setMessage(error.message)
      } else if (typeof error === 'string') {
        setMessage(error)
      } else {
        setMessage('Download failed')
      }
    }
  }

  const handleReset = () => {
    setStatus('idle')
    setMessage('')
    setDownloadUrl(null)
    setContentInfo(null)
    setTranscriptionResult(null)
    setUrl('')
  }

  const handleTranscribe = async () => {
    if (!url.trim()) {
      setStatus('error')
      setMessage('Please enter a valid URL')
      return
    }

    setStatus('loading')
    setMessage('Transcribing audio...')
    setTranscriptionResult(null)

    try {
      const response = await fetch('/api/transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          model: whisperModel,
          output_format: transcriptionFormat,
        }),
      })

      if (!response.ok) {
        const text = await response.text()
        let errorMsg = 'Transcription failed'
        try {
          const data = JSON.parse(text)
          errorMsg = data.detail || errorMsg
        } catch {
          errorMsg = text || errorMsg
        }
        throw new Error(errorMsg)
      }

      const data = await response.json()
      const jobId = data.job_id

      // Poll for job completion
      let attempts = 0
      const maxAttempts = 1800 // 30 minutes for long audio

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000))

        const statusResponse = await fetch(`/api/transcribe/${jobId}`)
        const statusData = await statusResponse.json()

        if (statusData.status === 'completed') {
          setStatus('success')
          setMessage('Transcription complete!')
          setTranscriptionResult({
            text: statusData.text,
            language: statusData.language,
            language_probability: statusData.language_probability,
            duration_seconds: statusData.duration_seconds,
            formatted_output: statusData.formatted_output,
            output_format: statusData.output_format,
          })
          return
        } else if (statusData.status === 'failed') {
          throw new Error(statusData.error || 'Transcription failed')
        }

        if (attempts % 10 === 0) {
          const progress = Math.min(Math.floor(attempts / 18), 95)
          setMessage(`Transcribing audio... ${progress}%`)
        }

        attempts++
      }

      throw new Error('Transcription timed out')
    } catch (error) {
      setStatus('error')
      if (error instanceof TypeError && error.message.includes('fetch')) {
        setMessage('Cannot connect to server. Make sure the backend is running.')
      } else if (error instanceof Error) {
        setMessage(error.message)
      } else {
        setMessage('Transcription failed')
      }
    }
  }

  const handleCopyTranscription = async () => {
    if (transcriptionResult) {
      await navigator.clipboard.writeText(transcriptionResult.formatted_output)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleDownloadTranscription = () => {
    if (transcriptionResult) {
      const ext = transcriptionFormat === 'json' ? 'json' : transcriptionFormat === 'text' ? 'txt' : transcriptionFormat
      const blob = new Blob([transcriptionResult.formatted_output], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `transcription.${ext}`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  // Transcription success view
  if (status === 'success' && transcriptionResult) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
        <div className="w-full max-w-2xl">
          <div className="text-center mb-8">
            <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
              Transcription Complete
            </h1>
            <p className="text-muted-foreground">
              Language: {transcriptionResult.language} ({(transcriptionResult.language_probability * 100).toFixed(0)}%) • Duration: {formatDuration(transcriptionResult.duration_seconds)}
            </p>
          </div>

          <div className="bg-card rounded-xl shadow-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                <span className="font-medium">Transcript</span>
                <span className="text-xs text-muted-foreground uppercase">({transcriptionResult.output_format})</span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleCopyTranscription}>
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div className="bg-muted rounded-lg p-4 max-h-80 overflow-y-auto">
              <pre className="text-sm whitespace-pre-wrap font-mono">{transcriptionResult.formatted_output}</pre>
            </div>
          </div>

          <div className="flex gap-3">
            <Button onClick={handleReset} variant="outline" className="flex-1 h-12 text-muted-foreground">
              <ArrowLeft className="mr-2 h-5 w-5" />
              Back
            </Button>
            <Button onClick={handleDownloadTranscription} className="flex-1 h-12">
              <Download className="mr-2 h-5 w-5" />
              Download
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Download success view
  if (status === 'success' && contentInfo && downloadUrl) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
        <div className="w-full max-w-xl">
          <div className="text-center mb-8">
            <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
              Download Ready
            </h1>
            <p className="text-muted-foreground">
              Your {mediaType} is ready to download
            </p>
          </div>

          <div className="bg-primary rounded-2xl p-6 sm:p-8 mb-6 relative overflow-hidden">
            <div className="absolute top-4 right-4">
              {mediaType === 'audio' ? (
                <Mic className="h-5 w-5 text-primary-foreground/60" />
              ) : (
                <Video className="h-5 w-5 text-primary-foreground/60" />
              )}
            </div>

            <div className="flex justify-center mb-4">
              <img src="/logo.svg" alt="AudioGrab" className="h-16 w-auto" />
            </div>

            <h2 className="text-xl sm:text-2xl font-semibold text-primary-foreground text-center mb-3">
              {contentInfo.title}
            </h2>

            <div className="flex items-center justify-center gap-2 text-primary-foreground/70 text-sm flex-wrap">
              {contentInfo.show_name && (
                <>
                  <span>{contentInfo.show_name}</span>
                  <span>•</span>
                </>
              )}
              {contentInfo.creator_name && (
                <>
                  <span>{contentInfo.creator_username ? `@${contentInfo.creator_username}` : contentInfo.creator_name}</span>
                  <span>•</span>
                </>
              )}
              {contentInfo.duration_seconds && (
                <>
                  <span>{formatDuration(contentInfo.duration_seconds)}</span>
                  <span>•</span>
                </>
              )}
              <span className="uppercase">{format}</span>
              {contentInfo.file_size_mb && (
                <>
                  <span>•</span>
                  <span>{contentInfo.file_size_mb.toFixed(1)} MB</span>
                </>
              )}
            </div>
          </div>

          <div className="flex gap-3">
            <Button onClick={handleReset} variant="outline" className="flex-1 h-12 text-muted-foreground">
              <ArrowLeft className="mr-2 h-5 w-5" />
              Back
            </Button>
            <Button asChild className="flex-1 h-12">
              <a href={downloadUrl} download>
                <Download className="mr-2 h-5 w-5" />
                Download
              </a>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Main view
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img src="/logo.svg" alt="AudioGrab" className="h-16 w-auto" />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
            AudioGrab
          </h1>
          <p className="text-muted-foreground">
            Download audio and video from your favorite platforms
          </p>
        </div>

        {/* Media Type Tabs */}
        <Tabs value={mediaType} onValueChange={handleMediaTypeChange} className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="audio" className="flex items-center gap-2">
              <FileAudio className="h-4 w-4" />
              Audio
            </TabsTrigger>
            <TabsTrigger value="video" className="flex items-center gap-2">
              <FileVideo className="h-4 w-4" />
              Video
            </TabsTrigger>
            <TabsTrigger value="transcribe" className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Transcribe
            </TabsTrigger>
          </TabsList>

          {/* Audio Tab */}
          <TabsContent value="audio">
            <Tabs value={platform} onValueChange={handlePlatformChange} className="w-full">
              <TabsList className="grid w-full grid-cols-5 mb-4">
                <TabsTrigger value="x_spaces" className="flex items-center gap-1 px-2">
                  <Twitter className="h-4 w-4" />
                  <span className="hidden lg:inline text-xs">Spaces</span>
                </TabsTrigger>
                <TabsTrigger value="apple_podcasts" className="flex items-center gap-1 px-2">
                  <Podcast className="h-4 w-4" />
                  <span className="hidden lg:inline text-xs">Apple</span>
                </TabsTrigger>
                <TabsTrigger value="spotify" className="flex items-center gap-1 px-2">
                  <Music className="h-4 w-4" />
                  <span className="hidden lg:inline text-xs">Spotify</span>
                </TabsTrigger>
                <TabsTrigger value="youtube" className="flex items-center gap-1 px-2">
                  <Youtube className="h-4 w-4" />
                  <span className="hidden lg:inline text-xs">YouTube</span>
                </TabsTrigger>
                <TabsTrigger value="xiaoyuzhou" className="flex items-center gap-1 px-2">
                  <Radio className="h-4 w-4" />
                  <span className="hidden lg:inline text-xs">小宇宙</span>
                </TabsTrigger>
              </TabsList>

              {AUDIO_PLATFORMS.map((p) => (
                <TabsContent key={p} value={p}>
                  <DownloadForm
                    platform={p}
                    url={url}
                    setUrl={setUrl}
                    format={format}
                    setFormat={setFormat}
                    status={status}
                    message={message}
                    onDownload={handleDownload}
                  />
                </TabsContent>
              ))}
            </Tabs>
          </TabsContent>

          {/* Video Tab */}
          <TabsContent value="video">
            <Tabs value={platform} onValueChange={handlePlatformChange} className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-4">
                <TabsTrigger value="x_video" className="flex items-center gap-2">
                  <Twitter className="h-4 w-4" />
                  X/Twitter
                </TabsTrigger>
                <TabsTrigger value="youtube_video" className="flex items-center gap-2">
                  <Youtube className="h-4 w-4" />
                  YouTube
                </TabsTrigger>
              </TabsList>

              {VIDEO_PLATFORMS.map((p) => (
                <TabsContent key={p} value={p}>
                  <DownloadForm
                    platform={p}
                    url={url}
                    setUrl={setUrl}
                    format={format}
                    setFormat={setFormat}
                    quality={quality}
                    setQuality={setQuality}
                    status={status}
                    message={message}
                    onDownload={handleDownload}
                    isVideo
                  />
                </TabsContent>
              ))}
            </Tabs>
          </TabsContent>

          {/* Transcribe Tab */}
          <TabsContent value="transcribe">
            <div className="bg-card rounded-xl shadow-lg p-6 sm:p-8">
              <div className="space-y-4">
                {/* URL Input */}
                <div>
                  <label htmlFor="transcribe-url" className="block text-sm font-medium text-foreground mb-2">
                    Audio/Video URL
                  </label>
                  <Input
                    id="transcribe-url"
                    type="url"
                    placeholder="https://youtube.com/watch?v=... or any supported URL"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && status !== 'loading') {
                        handleTranscribe()
                      }
                    }}
                    disabled={status === 'loading'}
                    className="h-12 text-base"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Supports: YouTube, X Spaces, Apple Podcasts, Spotify, 小宇宙
                  </p>
                </div>

                {/* Model Selector */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    <Mic className="inline h-4 w-4 mr-1" />
                    Whisper Model
                  </label>
                  <div className="grid gap-2 grid-cols-3 sm:grid-cols-6">
                    {WHISPER_MODELS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setWhisperModel(opt.value)}
                        disabled={status === 'loading'}
                        className={`p-2 rounded-lg border-2 transition-all ${
                          whisperModel === opt.value
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border bg-background text-foreground hover:border-primary/50'
                        } ${status === 'loading' ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                      >
                        <div className="font-semibold text-sm">{opt.label}</div>
                        <div className="text-xs text-muted-foreground">{opt.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Output Format Selector */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    <FileText className="inline h-4 w-4 mr-1" />
                    Output Format
                  </label>
                  <div className="grid gap-2 grid-cols-4">
                    {TRANSCRIPTION_FORMATS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setTranscriptionFormat(opt.value)}
                        disabled={status === 'loading'}
                        className={`p-3 rounded-lg border-2 transition-all ${
                          transcriptionFormat === opt.value
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border bg-background text-foreground hover:border-primary/50'
                        } ${status === 'loading' ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                      >
                        <div className="font-semibold">{opt.label}</div>
                        <div className="text-xs text-muted-foreground">{opt.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Transcribe Button */}
                <Button
                  onClick={handleTranscribe}
                  disabled={status === 'loading' || !url.trim()}
                  className="w-full h-12 text-base"
                  size="lg"
                >
                  {status === 'loading' ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      Transcribing...
                    </>
                  ) : (
                    <>
                      <FileText className="mr-2 h-5 w-5" />
                      Transcribe
                    </>
                  )}
                </Button>

                {/* Status Message */}
                {message && status !== 'success' && (
                  <div
                    className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
                      status === 'error'
                        ? 'bg-destructive/10 text-destructive'
                        : 'bg-primary/10 text-primary'
                    }`}
                  >
                    {status === 'error' && <AlertCircle className="h-4 w-4 flex-shrink-0" />}
                    {status === 'loading' && <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />}
                    <span>{message}</span>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Supports public content with replay/download enabled
        </p>
      </div>
    </div>
  )
}

interface DownloadFormProps {
  platform: Platform
  url: string
  setUrl: (url: string) => void
  format: string
  setFormat: (format: string) => void
  quality?: string
  setQuality?: (quality: string) => void
  status: DownloadStatus
  message: string
  onDownload: () => void
  isVideo?: boolean
}

function DownloadForm({
  platform,
  url,
  setUrl,
  format,
  setFormat,
  quality,
  setQuality,
  status,
  message,
  onDownload,
  isVideo,
}: DownloadFormProps) {
  return (
    <div className="bg-card rounded-xl shadow-lg p-6 sm:p-8">
      <div className="space-y-4">
        {/* URL Input */}
        <div>
          <label htmlFor="url-input" className="block text-sm font-medium text-foreground mb-2">
            {PLATFORM_LABELS[platform]} URL
          </label>
          <Input
            id="url-input"
            type="url"
            placeholder={PLATFORM_PLACEHOLDERS[platform]}
            value={url}
            onChange={(e) => {
              setUrl(e.target.value)
              if (status !== 'loading') {
                // Reset status on input change
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && status !== 'loading') {
                onDownload()
              }
            }}
            disabled={status === 'loading'}
            className="h-12 text-base"
          />
        </div>

        {/* Format Selector */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            {isVideo ? <FileVideo className="inline h-4 w-4 mr-1" /> : <FileAudio className="inline h-4 w-4 mr-1" />}
            Output Format
          </label>
          <div className={`grid gap-2 grid-cols-${PLATFORM_FORMATS[platform].length}`}>
            {PLATFORM_FORMATS[platform].map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFormat(opt.value)}
                disabled={status === 'loading'}
                className={`p-3 rounded-lg border-2 transition-all ${
                  format === opt.value
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-background text-foreground hover:border-primary/50'
                } ${status === 'loading' ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <div className="font-semibold">{opt.label}</div>
                <div className="text-xs text-muted-foreground">{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Quality Selector (Video only) */}
        {isVideo && setQuality && (
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Quality
            </label>
            <div className="grid gap-2 grid-cols-3">
              {QUALITY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setQuality(opt.value)}
                  disabled={status === 'loading'}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    quality === opt.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-background text-foreground hover:border-primary/50'
                  } ${status === 'loading' ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  <div className="font-semibold">{opt.label}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Download Button */}
        <Button
          onClick={onDownload}
          disabled={status === 'loading' || !url.trim()}
          className="w-full h-12 text-base"
          size="lg"
        >
          {status === 'loading' ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Downloading...
            </>
          ) : (
            <>
              <Download className="mr-2 h-5 w-5" />
              Download {isVideo ? 'Video' : 'Audio'}
            </>
          )}
        </Button>

        {/* Status Message */}
        {message && status !== 'success' && (
          <div
            className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
              status === 'error'
                ? 'bg-destructive/10 text-destructive'
                : 'bg-primary/10 text-primary'
            }`}
          >
            {status === 'error' && <AlertCircle className="h-4 w-4 flex-shrink-0" />}
            {status === 'loading' && <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />}
            <span>{message}</span>
          </div>
        )}
      </div>
    </div>
  )
}
