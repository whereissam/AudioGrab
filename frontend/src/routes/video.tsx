import { createFileRoute } from '@tanstack/react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useState } from 'react'
import { Twitter, Youtube } from 'lucide-react'
import {
  DownloadStatus,
  Platform,
  ContentInfo,
  VIDEO_PLATFORMS,
  PLATFORM_FORMATS,
  PLATFORM_LABELS,
} from '@/components/downloader'
import { DownloadForm, DownloadSuccess } from '@/components/downloader'

export const Route = createFileRoute('/video')({
  component: VideoPage,
})

function VideoPage() {
  const [platform, setPlatform] = useState<Platform>('x_video')
  const [url, setUrl] = useState('')
  const [format, setFormat] = useState<string>('mp4')
  const [quality, setQuality] = useState<string>('high')
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
        body: JSON.stringify({ url, format, platform, quality }),
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
      <DownloadSuccess
        contentInfo={contentInfo}
        downloadUrl={downloadUrl}
        format={format}
        mediaType="video"
        onReset={handleReset}
      />
    )
  }

  return (
    <Tabs value={platform} onValueChange={handlePlatformChange} className="w-full">
      <TabsList className="grid w-full grid-cols-2 mb-4 h-11 sm:h-10">
        <TabsTrigger value="x_video" className="flex items-center justify-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
          <Twitter className="h-4 w-4" />
          <span>X/Twitter</span>
        </TabsTrigger>
        <TabsTrigger value="youtube_video" className="flex items-center justify-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
          <Youtube className="h-4 w-4" />
          <span>YouTube</span>
        </TabsTrigger>
      </TabsList>

      <div className="bg-card rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
        {VIDEO_PLATFORMS.map((p) => (
          <TabsContent key={p} value={p} className="mt-0">
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
      </div>
    </Tabs>
  )
}
