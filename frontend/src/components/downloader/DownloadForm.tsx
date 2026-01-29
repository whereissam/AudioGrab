import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Download, Loader2, AlertCircle, FileAudio, FileVideo } from 'lucide-react'
import {
  Platform,
  DownloadStatus,
  PLATFORM_FORMATS,
  PLATFORM_PLACEHOLDERS,
  PLATFORM_LABELS,
  QUALITY_OPTIONS,
} from './types'

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

export function DownloadForm({
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
          onChange={(e) => setUrl(e.target.value)}
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
        <div className="grid gap-2 grid-cols-2">
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
  )
}
