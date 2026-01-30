import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Download, ArrowLeft, Mic, Video, FileText, Copy, Check, Users, Pencil, Sparkles, Loader2, ChevronDown } from 'lucide-react'
import { ContentInfo, TranscriptionResult, TranscriptionSegment, formatDuration } from './types'
import { useState, useMemo } from 'react'

const SUMMARY_TYPES = [
  { value: 'bullet_points', label: 'Bullet Points', desc: 'Key ideas as bullets' },
  { value: 'chapters', label: 'Chapters', desc: 'With timestamps' },
  { value: 'key_topics', label: 'Key Topics', desc: 'Major themes' },
  { value: 'action_items', label: 'Action Items', desc: 'Tasks & follow-ups' },
  { value: 'full', label: 'Full Summary', desc: 'Comprehensive' },
] as const

type SummaryType = typeof SUMMARY_TYPES[number]['value']

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
  onDownload: (renamedOutput?: string) => void
}

function formatTime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  const ms = Math.floor((seconds % 1) * 1000)
  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`
  }
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`
}

function formatSegmentsWithSpeakers(segments: TranscriptionSegment[], speakerNames: Record<string, string>): string {
  return segments.map(seg => {
    const speaker = seg.speaker ? (speakerNames[seg.speaker] || seg.speaker) : ''
    const time = `[${formatTime(seg.start)} -> ${formatTime(seg.end)}]`
    return speaker ? `${speaker}: ${seg.text}` : seg.text
  }).join('\n\n')
}

export function TranscriptionSuccess({
  result,
  onReset,
  onDownload,
}: TranscriptionSuccessProps) {
  const [copied, setCopied] = useState(false)
  const [showRenaming, setShowRenaming] = useState(false)
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({})

  // Summarization state
  const [showSummary, setShowSummary] = useState(false)
  const [summaryType, setSummaryType] = useState<SummaryType>('bullet_points')
  const [summary, setSummary] = useState<string | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [summaryCopied, setSummaryCopied] = useState(false)

  // Extract unique speakers from segments
  const uniqueSpeakers = useMemo(() => {
    if (!result.segments) return []
    const speakers = new Set<string>()
    result.segments.forEach(seg => {
      if (seg.speaker) speakers.add(seg.speaker)
    })
    return Array.from(speakers).sort()
  }, [result.segments])

  // Apply speaker renaming to formatted output
  const displayOutput = useMemo(() => {
    if (!result.diarized || Object.keys(speakerNames).length === 0) {
      return result.formatted_output
    }
    // Replace speaker names in the output
    let output = result.formatted_output
    for (const [original, renamed] of Object.entries(speakerNames)) {
      if (renamed && renamed !== original) {
        // Replace "Speaker X:" or "SPEAKER X:" patterns
        const pattern = new RegExp(`\\b${original}:`, 'gi')
        output = output.replace(pattern, `${renamed}:`)
      }
    }
    return output
  }, [result.formatted_output, result.diarized, speakerNames])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(displayOutput)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    onDownload(displayOutput !== result.formatted_output ? displayOutput : undefined)
  }

  const handleSpeakerRename = (speaker: string, newName: string) => {
    setSpeakerNames(prev => ({
      ...prev,
      [speaker]: newName
    }))
  }

  const handleSummarize = async () => {
    setSummaryLoading(true)
    setSummaryError(null)
    setSummary(null)

    try {
      const response = await fetch('/api/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: result.text,
          summary_type: summaryType,
        }),
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.detail || 'Summarization failed')
      }

      const data = await response.json()
      setSummary(data.content)
      setShowSummary(true)
    } catch (error) {
      setSummaryError(error instanceof Error ? error.message : 'Summarization failed')
    } finally {
      setSummaryLoading(false)
    }
  }

  const handleCopySummary = async () => {
    if (!summary) return
    await navigator.clipboard.writeText(summary)
    setSummaryCopied(true)
    setTimeout(() => setSummaryCopied(false), 2000)
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="text-center mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-foreground mb-2">
          Transcription Complete
        </h1>
        <p className="text-muted-foreground">
          Language: {result.language} ({(result.language_probability * 100).toFixed(0)}%) • Duration: {formatDuration(result.duration_seconds)}
          {result.diarized && ` • ${uniqueSpeakers.length} speaker${uniqueSpeakers.length !== 1 ? 's' : ''}`}
        </p>
      </div>

      {/* Speaker Renaming Panel */}
      {result.diarized && uniqueSpeakers.length > 0 && (
        <div className="bg-card rounded-xl shadow-lg p-4 mb-4">
          <button
            onClick={() => setShowRenaming(!showRenaming)}
            className="flex items-center gap-2 w-full text-left"
          >
            <Users className="h-5 w-5 text-primary" />
            <span className="font-medium flex-1">Rename Speakers</span>
            <Pencil className={`h-4 w-4 text-muted-foreground transition-transform ${showRenaming ? 'rotate-45' : ''}`} />
          </button>
          {showRenaming && (
            <div className="mt-4 space-y-3">
              {uniqueSpeakers.map(speaker => (
                <div key={speaker} className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground w-24 flex-shrink-0">{speaker}:</span>
                  <Input
                    type="text"
                    placeholder={`e.g., Host, Guest, ${speaker.replace('Speaker ', 'Person ')}`}
                    value={speakerNames[speaker] || ''}
                    onChange={(e) => handleSpeakerRename(speaker, e.target.value)}
                    className="h-8 flex-1"
                  />
                </div>
              ))}
              <p className="text-xs text-muted-foreground">
                Renamed speakers will be reflected in the transcript below and in downloads.
              </p>
            </div>
          )}
        </div>
      )}

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
          <pre className="text-sm whitespace-pre-wrap font-mono">{displayOutput}</pre>
        </div>
      </div>

      {/* Summarization Section */}
      <div className="bg-card rounded-xl shadow-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="h-5 w-5 text-primary" />
          <span className="font-medium">AI Summary</span>
        </div>

        {/* Summary Type Selector */}
        <div className="flex flex-wrap gap-2 mb-4">
          {SUMMARY_TYPES.map((type) => (
            <button
              key={type.value}
              onClick={() => setSummaryType(type.value)}
              disabled={summaryLoading}
              className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                summaryType === type.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              } ${summaryLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              {type.label}
            </button>
          ))}
        </div>

        {/* Generate Button */}
        <Button
          onClick={handleSummarize}
          disabled={summaryLoading}
          className="w-full mb-4"
          variant={summary ? 'outline' : 'default'}
        >
          {summaryLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              {summary ? 'Regenerate Summary' : 'Generate Summary'}
            </>
          )}
        </Button>

        {/* Error Message */}
        {summaryError && (
          <div className="bg-destructive/10 text-destructive rounded-lg p-3 mb-4 text-sm">
            {summaryError}
          </div>
        )}

        {/* Summary Result */}
        {summary && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {SUMMARY_TYPES.find(t => t.value === summaryType)?.label}
              </span>
              <Button variant="outline" size="sm" onClick={handleCopySummary}>
                {summaryCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            <div className="bg-muted rounded-lg p-4 max-h-60 overflow-y-auto">
              <div className="text-sm whitespace-pre-wrap prose prose-sm dark:prose-invert max-w-none">
                {summary}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <Button onClick={onReset} variant="outline" className="flex-1 h-12 text-muted-foreground">
          <ArrowLeft className="mr-2 h-5 w-5" />
          Back
        </Button>
        <Button onClick={handleDownload} className="flex-1 h-12">
          <Download className="mr-2 h-5 w-5" />
          Download
        </Button>
      </div>
    </div>
  )
}
