import { Button } from '@/components/ui/button'
import { Download, ArrowLeft, Mic, Video, FileText, Copy, Check } from 'lucide-react'
import { ContentInfo, TranscriptionResult, formatDuration } from './types'
import { useState } from 'react'

interface DownloadSuccessProps {
  contentInfo: ContentInfo
  downloadUrl: string
  format: string
  mediaType: 'audio' | 'video'
  onReset: () => void
}

export function DownloadSuccess({
  contentInfo,
  downloadUrl,
  format,
  mediaType,
  onReset,
}: DownloadSuccessProps) {
  return (
    <div className="w-full max-w-xl mx-auto">
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
        <Button onClick={onReset} variant="outline" className="flex-1 h-12 text-muted-foreground">
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
  )
}

interface TranscriptionSuccessProps {
  result: TranscriptionResult
  onReset: () => void
  onDownload: () => void
}

export function TranscriptionSuccess({
  result,
  onReset,
  onDownload,
}: TranscriptionSuccessProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.formatted_output)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
          Transcription Complete
        </h1>
        <p className="text-muted-foreground">
          Language: {result.language} ({(result.language_probability * 100).toFixed(0)}%) • Duration: {formatDuration(result.duration_seconds)}
        </p>
      </div>

      <div className="bg-card rounded-xl shadow-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            <span className="font-medium">Transcript</span>
            <span className="text-xs text-muted-foreground uppercase">({result.output_format})</span>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        <div className="bg-muted rounded-lg p-4 max-h-80 overflow-y-auto">
          <pre className="text-sm whitespace-pre-wrap font-mono">{result.formatted_output}</pre>
        </div>
      </div>

      <div className="flex gap-3">
        <Button onClick={onReset} variant="outline" className="flex-1 h-12 text-muted-foreground">
          <ArrowLeft className="mr-2 h-5 w-5" />
          Back
        </Button>
        <Button onClick={onDownload} className="flex-1 h-12">
          <Download className="mr-2 h-5 w-5" />
          Download
        </Button>
      </div>
    </div>
  )
}
