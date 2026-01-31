import { createFileRoute } from '@tanstack/react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useState } from 'react'
import { Twitter, Podcast, Music, Youtube, Radio } from 'lucide-react'
import {
  DownloadStatus,
  Platform,
  ContentInfo,
  AUDIO_PLATFORMS,
  PLATFORM_FORMATS,
  PLATFORM_LABELS,
} from '@/components/downloader'
import { DownloadForm, DownloadSuccess } from '@/components/downloader'

export const Route = createFileRoute('/audio')({
  component: AudioPage,
})

function AudioPage() {
  const [platform, setPlatform] = useState<Platform>('x_spaces')
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<string>('m4a')
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

  const handleReset = () => {
    setStatus('idle')
    setMessage('')
    setDownloadUrl(null)
    setContentInfo(null)
    setUrl('')
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
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Download failed')
      }

      const data = await response.json()
      const jobId = data.job_id

      for (let i = 0; i < 600; i++) {
        await new Promise(r => setTimeout(r, 1000))
        const res = await fetch(`/api/download/${jobId}`)
        const job = await res.json()

        if (job.status === 'completed') {
          setStatus('success')
          setDownloadUrl(`/api/download/${jobId}/file`)
          const info = job.content_info || job.space_info
          setContentInfo({
            title: info?.title || 'Downloaded Media',
            creator_name: info?.creator_name,
            creator_username: info?.creator_username,
            duration_seconds: info?.duration_seconds,
            file_size_mb: job.file_size_mb,
            show_name: info?.show_name,
          })
          return
        } else if (job.status === 'failed') {
          throw new Error(job.error || 'Download failed')
        }

        if (i % 10 === 0) {
          setMessage(`Downloading... ${Math.min(Math.floor(i / 6), 95)}%`)
        }
      }
      throw new Error('Download timed out')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Download failed')
    }
  }

  if (status === 'success' && contentInfo && downloadUrl) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <DownloadSuccess
          contentInfo={contentInfo}
          downloadUrl={downloadUrl}
          format={format}
          mediaType="audio"
          onReset={handleReset}
        />
      </div>
    )
  }

  return (
    <div className="flex-1 flex items-center justify-center p-3 sm:p-4">
      <div className="w-full max-w-xl">
        <Tabs value={platform} onValueChange={handlePlatformChange} className="w-full">
          <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0 mb-4 text-muted-foreground">
            <TabsList className="inline-flex w-auto min-w-full sm:grid sm:grid-cols-5 gap-1">
              <TabsTrigger value="x_spaces" className="flex items-center gap-1.5 px-3 sm:px-2 whitespace-nowrap">
                <Twitter className="h-4 w-4 flex-shrink-0" />
                <span className="text-xs">Spaces</span>
              </TabsTrigger>
              <TabsTrigger value="apple_podcasts" className="flex items-center gap-1.5 px-3 sm:px-2 whitespace-nowrap">
                <Podcast className="h-4 w-4 flex-shrink-0" />
                <span className="text-xs">Apple</span>
              </TabsTrigger>
              <TabsTrigger value="spotify" className="flex items-center gap-1.5 px-3 sm:px-2 whitespace-nowrap">
                <Music className="h-4 w-4 flex-shrink-0" />
                <span className="text-xs">Spotify</span>
              </TabsTrigger>
              <TabsTrigger value="youtube" className="flex items-center gap-1.5 px-3 sm:px-2 whitespace-nowrap">
                <Youtube className="h-4 w-4 flex-shrink-0" />
                <span className="text-xs">YouTube</span>
              </TabsTrigger>
              <TabsTrigger value="xiaoyuzhou" className="flex items-center gap-1.5 px-3 sm:px-2 whitespace-nowrap">
                <Radio className="h-4 w-4 flex-shrink-0" />
                <span className="text-xs">小宇宙</span>
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="bg-card rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
            {AUDIO_PLATFORMS.map((p) => (
              <TabsContent key={p} value={p} className="mt-0">
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
          </div>
        </Tabs>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Supports public content with replay/download enabled
        </p>
      </div>
    </div>
  )
}
