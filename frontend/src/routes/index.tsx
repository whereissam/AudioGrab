import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useState } from 'react'
import { Download, Loader2, AlertCircle, ArrowLeft, Mic, FileAudio, Twitter, Podcast, Music } from 'lucide-react'

type DownloadStatus = 'idle' | 'loading' | 'success' | 'error'
type AudioFormat = 'm4a' | 'mp3' | 'mp4'
type Platform = 'x_spaces' | 'apple_podcasts' | 'spotify'

interface ContentInfo {
  title: string
  creator_name?: string
  creator_username?: string
  duration_seconds?: number
  file_size_mb?: number
  show_name?: string
  platform?: Platform
}

const PLATFORM_FORMATS: Record<Platform, { value: AudioFormat; label: string; desc: string }[]> = {
  x_spaces: [
    { value: 'm4a', label: 'M4A', desc: 'Original quality' },
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
    { value: 'mp4', label: 'MP4', desc: 'Video container' },
  ],
  apple_podcasts: [
    { value: 'm4a', label: 'M4A', desc: 'Original quality' },
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
  ],
  spotify: [
    { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
    { value: 'm4a', label: 'M4A', desc: 'AAC format' },
  ],
}

const PLATFORM_PLACEHOLDERS: Record<Platform, string> = {
  x_spaces: 'https://x.com/i/spaces/1vOxwdyYrlqKB',
  apple_podcasts: 'https://podcasts.apple.com/us/podcast/show-name/id123456789',
  spotify: 'https://open.spotify.com/episode/abc123',
}

const PLATFORM_LABELS: Record<Platform, string> = {
  x_spaces: 'X Spaces',
  apple_podcasts: 'Apple Podcasts',
  spotify: 'Spotify',
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
  const [platform, setPlatform] = useState<Platform>('x_spaces')
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<AudioFormat>('m4a')
  const [status, setStatus] = useState<DownloadStatus>('idle')
  const [message, setMessage] = useState('')
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [contentInfo, setContentInfo] = useState<ContentInfo | null>(null)

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
        body: JSON.stringify({ url, format, platform }),
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
      const maxAttempts = 300 // 5 minutes for Spotify (can be slow)

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000))

        const statusResponse = await fetch(`/api/download/${jobId}`)
        const statusData = await statusResponse.json()

        if (statusData.status === 'completed') {
          setStatus('success')
          setMessage('Download complete!')
          setDownloadUrl(`/api/download/${jobId}/file`)

          // Set content info (use content_info or space_info for backward compat)
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
              title: 'Downloaded Audio',
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

        // Update progress message
        if (attempts % 10 === 0) {
          const progress = Math.min(Math.floor(attempts / 3), 95)
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
    setUrl('')
  }

  // Success view with content card
  if (status === 'success' && contentInfo && downloadUrl) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
        <div className="w-full max-w-xl">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
              Download Ready
            </h1>
            <p className="text-muted-foreground">
              Your audio is ready to download
            </p>
          </div>

          {/* Content Card */}
          <div className="bg-primary rounded-2xl p-6 sm:p-8 mb-6 relative overflow-hidden">
            {/* Icon in corner */}
            <div className="absolute top-4 right-4">
              <Mic className="h-5 w-5 text-primary-foreground/60" />
            </div>

            {/* Logo */}
            <div className="flex justify-center mb-4">
              <img
                src="/logo.svg"
                alt="AudioGrab"
                className="h-16 w-auto"
              />
            </div>

            {/* Title */}
            <h2 className="text-xl sm:text-2xl font-semibold text-primary-foreground text-center mb-3">
              {contentInfo.title}
            </h2>

            {/* Meta info */}
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

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              onClick={handleReset}
              variant="outline"
              className="flex-1 h-12 text-muted-foreground"
            >
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

  // Default input view with tabs
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img
              src="/logo.svg"
              alt="AudioGrab"
              className="h-16 w-auto"
            />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
            AudioGrab
          </h1>
          <p className="text-muted-foreground">
            Download audio from X Spaces, Apple Podcasts, and Spotify
          </p>
        </div>

        {/* Platform Tabs */}
        <Tabs value={platform} onValueChange={handlePlatformChange} className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="x_spaces" className="flex items-center gap-2">
              <Twitter className="h-4 w-4" />
              <span className="hidden sm:inline">X Spaces</span>
              <span className="sm:hidden">X</span>
            </TabsTrigger>
            <TabsTrigger value="apple_podcasts" className="flex items-center gap-2">
              <Podcast className="h-4 w-4" />
              <span className="hidden sm:inline">Apple</span>
              <span className="sm:hidden">Apple</span>
            </TabsTrigger>
            <TabsTrigger value="spotify" className="flex items-center gap-2">
              <Music className="h-4 w-4" />
              <span className="hidden sm:inline">Spotify</span>
              <span className="sm:hidden">Spotify</span>
            </TabsTrigger>
          </TabsList>

          {/* Tab Content - Same form for all platforms */}
          {(['x_spaces', 'apple_podcasts', 'spotify'] as Platform[]).map((p) => (
            <TabsContent key={p} value={p}>
              <div className="bg-card rounded-xl shadow-lg p-6 sm:p-8">
                <div className="space-y-4">
                  {/* URL Input */}
                  <div>
                    <label htmlFor="url-input" className="block text-sm font-medium text-foreground mb-2">
                      {PLATFORM_LABELS[p]} URL
                    </label>
                    <Input
                      id="url-input"
                      type="url"
                      placeholder={PLATFORM_PLACEHOLDERS[p]}
                      value={url}
                      onChange={(e) => {
                        setUrl(e.target.value)
                        if (status !== 'loading') {
                          setStatus('idle')
                          setMessage('')
                        }
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && status !== 'loading') {
                          handleDownload()
                        }
                      }}
                      disabled={status === 'loading'}
                      className="h-12 text-base"
                    />
                  </div>

                  {/* Format Selector */}
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-2">
                      <FileAudio className="inline h-4 w-4 mr-1" />
                      Output Format
                    </label>
                    <div className={`grid gap-2 ${PLATFORM_FORMATS[p].length === 3 ? 'grid-cols-3' : 'grid-cols-2'}`}>
                      {PLATFORM_FORMATS[p].map((opt) => (
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

                  {/* Download Button */}
                  <Button
                    onClick={handleDownload}
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
                        Download as {format.toUpperCase()}
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
          ))}
        </Tabs>

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          Supports public content with replay/download enabled
        </p>
      </div>
    </div>
  )
}
