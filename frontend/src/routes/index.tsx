import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useState } from 'react'
import { Download, Loader2, AlertCircle, ArrowLeft, Mic, FileAudio } from 'lucide-react'

type DownloadStatus = 'idle' | 'loading' | 'success' | 'error'
type AudioFormat = 'm4a' | 'mp3' | 'mp4'

interface SpaceInfo {
  title: string
  host_username?: string
  host_display_name?: string
  duration_seconds?: number
  file_size_mb?: number
}

const FORMAT_OPTIONS: { value: AudioFormat; label: string; desc: string }[] = [
  { value: 'm4a', label: 'M4A', desc: 'Original quality' },
  { value: 'mp3', label: 'MP3', desc: 'Most compatible' },
  { value: 'mp4', label: 'MP4', desc: 'Video container' },
]

export const Route = createFileRoute('/')({
  component: SpaceDownloader,
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

function SpaceDownloader() {
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<AudioFormat>('m4a')
  const [status, setStatus] = useState<DownloadStatus>('idle')
  const [message, setMessage] = useState('')
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const [spaceInfo, setSpaceInfo] = useState<SpaceInfo | null>(null)

  const isValidUrl = (input: string) => {
    return /(?:twitter\.com|x\.com)\/i\/spaces\/[a-zA-Z0-9]+/.test(input)
  }

  const handleDownload = async () => {
    if (!url.trim() || !isValidUrl(url)) {
      setStatus('error')
      setMessage('Please enter a valid X Space URL')
      return
    }

    setStatus('loading')
    setMessage('Downloading Space...')
    setDownloadUrl(null)
    setSpaceInfo(null)

    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, format }),
      })

      if (!response.ok) {
        const text = await response.text()
        let errorMsg = 'Download failed'
        try {
          const data = JSON.parse(text)
          // FastAPI validation errors return detail as an array of error objects
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
      const maxAttempts = 180 // 3 minutes

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000))

        const statusResponse = await fetch(`/api/download/${jobId}`)
        const statusData = await statusResponse.json()

        if (statusData.status === 'completed') {
          setStatus('success')
          setMessage('Download complete!')
          setDownloadUrl(`/api/download/${jobId}/file`)

          // Set space info
          if (statusData.space_info) {
            setSpaceInfo({
              title: statusData.space_info.title || 'Twitter Space',
              host_username: statusData.space_info.host_username,
              host_display_name: statusData.space_info.host_display_name,
              duration_seconds: statusData.space_info.duration_seconds,
              file_size_mb: statusData.file_size_mb,
            })
          } else {
            setSpaceInfo({
              title: 'Twitter Space',
              file_size_mb: statusData.file_size_mb,
            })
          }
          return
        } else if (statusData.status === 'failed') {
          // Extract error message - handle case where error might be an object
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
          setMessage(`Downloading Space... ${Math.min(Math.floor(attempts / 2), 95)}%`)
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
    setSpaceInfo(null)
    setUrl('')
  }

  // Success view with Space card
  if (status === 'success' && spaceInfo && downloadUrl) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
        <div className="w-full max-w-xl">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
              Download Ready
            </h1>
            <p className="text-muted-foreground">
              Your Space audio is ready to download
            </p>
          </div>

          {/* Space Card */}
          <div className="bg-primary rounded-2xl p-6 sm:p-8 mb-6 relative overflow-hidden">
            {/* Mic icon in corner */}
            <div className="absolute top-4 right-4">
              <Mic className="h-5 w-5 text-primary-foreground/60" />
            </div>

            {/* Logo */}
            <div className="flex justify-center mb-4">
              <img
                src="/xdownlader-brand.webp"
                alt="xdownloader"
                className="h-16 w-auto"
              />
            </div>

            {/* Title */}
            <h2 className="text-xl sm:text-2xl font-semibold text-primary-foreground text-center mb-3">
              {spaceInfo.title}
            </h2>

            {/* Meta info */}
            <div className="flex items-center justify-center gap-2 text-primary-foreground/70 text-sm flex-wrap">
              {spaceInfo.host_display_name && (
                <>
                  <span>@{spaceInfo.host_username || spaceInfo.host_display_name}</span>
                  <span>•</span>
                </>
              )}
              {spaceInfo.duration_seconds && (
                <>
                  <span>{formatDuration(spaceInfo.duration_seconds)}</span>
                  <span>•</span>
                </>
              )}
              <span className="uppercase">{format}</span>
              {spaceInfo.file_size_mb && (
                <>
                  <span>•</span>
                  <span>{spaceInfo.file_size_mb.toFixed(1)} MB</span>
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

  // Default input view
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img
              src="/xdownlader-brand.webp"
              alt="xdownloader"
              className="h-16 w-auto"
            />
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
            X Spaces Downloader
          </h1>
          <p className="text-muted-foreground">
            Download Twitter/X Spaces audio recordings
          </p>
        </div>

        {/* Input Card */}
        <div className="bg-card rounded-xl shadow-lg p-6 sm:p-8">
          <div className="space-y-4">
            {/* URL Input */}
            <div>
              <label htmlFor="space-url" className="block text-sm font-medium text-foreground mb-2">
                Space URL
              </label>
              <Input
                id="space-url"
                type="url"
                placeholder="https://x.com/i/spaces/1vOxwdyYrlqKB"
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
              <div className="grid grid-cols-3 gap-2">
                {FORMAT_OPTIONS.map((opt) => (
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

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground mt-6">
          Supports public Spaces with replay enabled
        </p>
      </div>
    </div>
  )
}
