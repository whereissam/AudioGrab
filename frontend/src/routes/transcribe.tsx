import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import {
  DownloadStatus,
  WhisperModel,
  TranscriptionFormat,
  EnhancementPreset,
  TranscriptionResult,
} from '@/components/downloader'
import { TranscribeForm, TranscriptionSuccess } from '@/components/downloader'

export const Route = createFileRoute('/transcribe')({
  component: TranscribePage,
})

function TranscribePage() {
  const [url, setUrl] = useState('')
  const [status, setStatus] = useState<DownloadStatus>('idle')
  const [message, setMessage] = useState('')
  const [whisperModel, setWhisperModel] = useState<WhisperModel>('base')
  const [transcriptionFormat, setTranscriptionFormat] = useState<TranscriptionFormat>('text')
  const [transcriptionResult, setTranscriptionResult] = useState<TranscriptionResult | null>(null)
  const [transcriptionJobId, setTranscriptionJobId] = useState<string | null>(null)
  const [transcribeMode, setTranscribeMode] = useState<'url' | 'file'>('url')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [language, setLanguage] = useState<string>('')
  const [diarize, setDiarize] = useState(false)
  const [numSpeakers, setNumSpeakers] = useState<number | null>(null)
  const [enhance, setEnhance] = useState(false)
  const [enhancementPreset, setEnhancementPreset] = useState<EnhancementPreset>('medium')

  const handleReset = () => {
    setStatus('idle')
    setMessage('')
    setTranscriptionResult(null)
    setTranscriptionJobId(null)
    setUrl('')
    setSelectedFile(null)
    setLanguage('')
    setDiarize(false)
    setNumSpeakers(null)
    setEnhance(false)
    setEnhancementPreset('medium')
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

      for (let i = 0; i < 1800; i++) {
        await new Promise(r => setTimeout(r, 1000))
        const res = await fetch(`/api/transcribe/${jobId}`)
        const job = await res.json()

        if (job.status === 'completed') {
          setStatus('success')
          setTranscriptionJobId(jobId)
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
    const downloadUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = `transcription.${ext}`
    a.click()
    URL.revokeObjectURL(downloadUrl)
  }

  if (status === 'success' && transcriptionResult) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <TranscriptionSuccess
          result={transcriptionResult}
          jobId={transcriptionJobId}
          onReset={handleReset}
          onDownload={handleDownloadTranscription}
        />
      </div>
    )
  }

  return (
    <div className="flex-1 flex items-center justify-center p-3 sm:p-4">
      <div className="w-full max-w-xl">
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

        <p className="text-center text-xs text-muted-foreground mt-6">
          Transcribe audio and video to text with Whisper
        </p>
      </div>
    </div>
  )
}
