import { useRef, useEffect } from 'react'
import { Sparkles, FileText } from 'lucide-react'
import { TranscriptionSegment } from '@/hooks/useRealtimeTranscription'
import { formatDuration } from '@/components/downloader'

interface TranscriptDisplayProps {
  segments: TranscriptionSegment[]
  partialText: string
  autoScroll?: boolean
}

export function TranscriptDisplay({
  segments,
  partialText,
  autoScroll = true,
}: TranscriptDisplayProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    if (autoScroll && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [segments, partialText, autoScroll])

  const hasContent = segments.length > 0 || partialText

  return (
    <div
      ref={containerRef}
      className="h-64 overflow-y-auto bg-muted/50 rounded-lg p-4 font-mono text-sm"
    >
      {!hasContent ? (
        <div className="h-full flex items-center justify-center text-muted-foreground">
          <p>Transcript will appear here...</p>
        </div>
      ) : (
        <div className="space-y-2">
          {segments.map((segment, index) => (
            <div key={index} className="group">
              <span className="text-xs text-muted-foreground mr-2 opacity-60 group-hover:opacity-100 transition-opacity">
                [{formatDuration(segment.start)}]
              </span>
              <span className="text-foreground">{segment.text}</span>
            </div>
          ))}

          {/* Partial text (interim result) */}
          {partialText && (
            <div className="group">
              <span className="text-xs text-muted-foreground mr-2 opacity-60">
                [...]
              </span>
              <span className="text-muted-foreground italic">{partialText}</span>
              <span className="inline-block w-1 h-4 ml-1 bg-primary animate-pulse" />
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={endRef} />
        </div>
      )}
    </div>
  )
}

interface TranscriptStatsProps {
  duration: number
  segmentCount: number
  language: string | null
  llmPolished?: boolean
  tokensUsed?: number | null
}

export function TranscriptStats({
  duration,
  segmentCount,
  language,
  llmPolished,
  tokensUsed,
}: TranscriptStatsProps) {
  return (
    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
      <div>
        <span className="font-medium">Duration:</span> {formatDuration(duration)}
      </div>
      <div>
        <span className="font-medium">Segments:</span> {segmentCount}
      </div>
      {language && (
        <div>
          <span className="font-medium">Language:</span> {language.toUpperCase()}
        </div>
      )}
      {llmPolished && (
        <div className="flex items-center gap-1 text-primary">
          <Sparkles className="h-3 w-3" />
          <span>AI Polished</span>
          {tokensUsed && <span className="text-muted-foreground">({tokensUsed} tokens)</span>}
        </div>
      )}
    </div>
  )
}

interface FullTranscriptViewProps {
  fullText: string
  segments: TranscriptionSegment[]
  language: string | null
  duration: number
  onCopy: () => void
  onDownload: () => void
  llmPolished?: boolean
  tokensUsed?: number | null
  rawText?: string | null
  showRaw?: boolean
  onToggleRaw?: () => void
}

export function FullTranscriptView({
  fullText,
  segments,
  language,
  duration,
  onCopy,
  onDownload,
  llmPolished,
  tokensUsed,
  rawText,
  showRaw,
  onToggleRaw,
}: FullTranscriptViewProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Transcription Complete</h3>
        <TranscriptStats
          duration={duration}
          segmentCount={segments.length}
          language={language}
          llmPolished={llmPolished}
          tokensUsed={tokensUsed}
        />
      </div>

      {/* Toggle between polished and raw if both available */}
      {llmPolished && rawText && onToggleRaw && (
        <div className="flex gap-2">
          <button
            onClick={onToggleRaw}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
              !showRaw
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Polished
          </button>
          <button
            onClick={onToggleRaw}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
              showRaw
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:text-foreground'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            Original
          </button>
        </div>
      )}

      <div className="bg-muted/50 rounded-lg p-4 max-h-96 overflow-y-auto">
        <p className="text-sm whitespace-pre-wrap">{fullText}</p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={onCopy}
          className="flex-1 px-4 py-2 bg-secondary text-secondary-foreground rounded-lg hover:bg-secondary/80 transition-colors text-sm font-medium"
        >
          Copy to Clipboard
        </button>
        <button
          onClick={onDownload}
          className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
        >
          Download Transcript
        </button>
      </div>
    </div>
  )
}
