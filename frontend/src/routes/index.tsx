import { createFileRoute } from '@tanstack/react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useState } from 'react'
import { FileAudio, FileVideo, FileText, Twitter, Podcast, Music, Youtube, Radio } from 'lucide-react'
import {
  DownloadStatus,
  Platform,
  MediaType,
  WhisperModel,
  TranscriptionFormat,
  EnhancementPreset,
  ContentInfo,
  TranscriptionResult,
  AUDIO_PLATFORMS,
  VIDEO_PLATFORMS,
  PLATFORM_FORMATS,
  PLATFORM_LABELS,
} from '@/components/downloader'
import { DownloadForm, TranscribeForm, DownloadSuccess, TranscriptionSuccess } from '@/components/downloader'

export const Route = createFileRoute('/')({
  component: AudioGrabHome,
})

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
  const [transcribeMode, setTranscribeMode] = useState<'url' | 'file'>('url')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [language, setLanguage] = useState<string>('')  // Empty = auto-detect
  const [diarize, setDiarize] = useState(false)
  const [numSpeakers, setNumSpeakers] = useState<number | null>(null)
  const [enhance, setEnhance] = useState(false)
  const [enhancementPreset, setEnhancementPreset] = useState<EnhancementPreset>('medium')

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

  const handleReset = () => {
    setStatus('idle')
    setMessage('')
    setDownloadUrl(null)
    setContentInfo(null)
    setTranscriptionResult(null)
    setUrl('')
    setSelectedFile(null)
    setLanguage('')
    setDiarize(false)
    setNumSpeakers(null)
    setEnhance(false)
    setEnhancementPreset('medium')
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

      // Poll for completion
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

  const handleTranscribe = async () => {
    if (transcribeMode === 'url' && !url.trim()) {
      setStatus('error')
      setMessage('Please enter a valid URL')
      return
    }
    if (transcribeMode === 'file' && !selectedFile) {
      setStatus('error')
      setMessage('Please select a file')
      return
    }

    setStatus('loading')
    setMessage(transcribeMode === 'file' ? 'Uploading and transcribing...' : 'Transcribing...')
    setTranscriptionResult(null)

    try {
      let response: Response

      if (transcribeMode === 'file' && selectedFile) {
        const formData = new FormData()
        formData.append('file', selectedFile)
        formData.append('model', whisperModel)
        formData.append('output_format', transcriptionFormat)
        if (language) {
          formData.append('language', language)
        }
        if (diarize) {
          formData.append('diarize', 'true')
          if (numSpeakers) {
            formData.append('num_speakers', numSpeakers.toString())
          }
        }
        if (enhance) {
          formData.append('enhance', 'true')
          formData.append('enhancement_preset', enhancementPreset)
        }
        response = await fetch('/api/transcribe/upload', { method: 'POST', body: formData })
      } else {
        response = await fetch('/api/transcribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url,
            model: whisperModel,
            output_format: transcriptionFormat,
            language: language || undefined,
            diarize,
            num_speakers: numSpeakers,
            enhance,
            enhancement_preset: enhancementPreset,
          }),
        })
      }

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Transcription failed')
      }

      const data = await response.json()
      const jobId = data.job_id

      // Poll for completion
      for (let i = 0; i < 1800; i++) {
        await new Promise(r => setTimeout(r, 1000))
        const res = await fetch(`/api/transcribe/${jobId}`)
        const job = await res.json()

        if (job.status === 'completed') {
          setStatus('success')
          setTranscriptionResult({
            text: job.text,
            language: job.language,
            language_probability: job.language_probability,
            duration_seconds: job.duration_seconds,
            formatted_output: job.formatted_output,
            output_format: job.output_format,
            segments: job.segments,
            diarized: job.segments?.some((s: { speaker?: string }) => s.speaker),
          })
          return
        } else if (job.status === 'failed') {
          throw new Error(job.error || 'Transcription failed')
        }

        if (i % 10 === 0) {
          setMessage(`Transcribing... ${Math.min(Math.floor(i / 18), 95)}%`)
        }
      }
      throw new Error('Transcription timed out')
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Transcription failed')
    }
  }

  const handleDownloadTranscription = (renamedOutput?: string) => {
    if (!transcriptionResult) return
    const ext = transcriptionFormat === 'json' ? 'json' : transcriptionFormat === 'text' || transcriptionFormat === 'dialogue' ? 'txt' : transcriptionFormat
    const content = renamedOutput || transcriptionResult.formatted_output
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `transcription.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Success views
  if (status === 'success' && transcriptionResult) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
        <TranscriptionSuccess result={transcriptionResult} onReset={handleReset} onDownload={handleDownloadTranscription} />
      </div>
    )
  }

  if (status === 'success' && contentInfo && downloadUrl) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-4">
        <DownloadSuccess contentInfo={contentInfo} downloadUrl={downloadUrl} format={format} mediaType={mediaType === 'video' ? 'video' : 'audio'} onReset={handleReset} />
      </div>
    )
  }

  // Main view
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted flex items-center justify-center p-3 sm:p-4">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-6 sm:mb-8">
          <div className="flex justify-center mb-3 sm:mb-4">
            <img src="/logo.svg" alt="AudioGrab" className="h-12 sm:h-16 w-auto" />
          </div>
          <h1 className="text-2xl sm:text-4xl font-bold text-foreground mb-1 sm:mb-2">AudioGrab</h1>
          <p className="text-sm sm:text-base text-muted-foreground">Download audio and video from your favorite platforms</p>
        </div>

        {/* Tabs with fixed height content */}
        <Tabs value={mediaType} onValueChange={handleMediaTypeChange} className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-4 h-11 sm:h-10">
            <TabsTrigger value="audio" className="flex items-center justify-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
              <FileAudio className="h-4 w-4" />
              <span>Audio</span>
            </TabsTrigger>
            <TabsTrigger value="video" className="flex items-center justify-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
              <FileVideo className="h-4 w-4" />
              <span>Video</span>
            </TabsTrigger>
            <TabsTrigger value="transcribe" className="flex items-center justify-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
              <FileText className="h-4 w-4" />
              <span>Transcribe</span>
            </TabsTrigger>
          </TabsList>

          {/* Fixed height container to prevent layout shift */}
          <div className="min-h-[480px] sm:min-h-[420px]">
            <TabsContent value="audio" className="mt-0">
              <Tabs value={platform} onValueChange={handlePlatformChange} className="w-full">
                <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0 mb-4">
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
            </TabsContent>

            <TabsContent value="video" className="mt-0">
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
            </TabsContent>

            <TabsContent value="transcribe" className="mt-0">
              <div className="bg-card rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
                <TranscribeForm
                  url={url}
                  setUrl={setUrl}
                  transcribeMode={transcribeMode}
                  setTranscribeMode={setTranscribeMode}
                  selectedFile={selectedFile}
                  setSelectedFile={setSelectedFile}
                  whisperModel={whisperModel}
                  setWhisperModel={setWhisperModel}
                  transcriptionFormat={transcriptionFormat}
                  setTranscriptionFormat={setTranscriptionFormat}
                  language={language}
                  setLanguage={setLanguage}
                  enhance={enhance}
                  setEnhance={setEnhance}
                  enhancementPreset={enhancementPreset}
                  setEnhancementPreset={setEnhancementPreset}
                  diarize={diarize}
                  setDiarize={setDiarize}
                  numSpeakers={numSpeakers}
                  setNumSpeakers={setNumSpeakers}
                  status={status}
                  message={message}
                  onTranscribe={handleTranscribe}
                />
              </div>
            </TabsContent>
          </div>
        </Tabs>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Supports public content with replay/download enabled
        </p>
      </div>
    </div>
  )
}
