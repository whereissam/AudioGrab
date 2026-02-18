import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { SearchableSelect } from '@/components/ui/searchable-select'
import { Download, ArrowLeft, Mic, Video, FileText, Copy, Check, Users, Sparkles, Loader2, ChevronDown, Languages, Scissors, BookOpen, Settings, ExternalLink } from 'lucide-react'
import { ContentInfo, TranscriptionResult, formatDuration } from './types'
import { useState, useMemo, useEffect } from 'react'
import { SentimentSection } from '@/components/sentiment'
import { ExtractSection } from '@/components/extract'

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
    <div className="w-full max-w-xl mx-auto px-1">
      <div className="text-center mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-4xl font-bold text-foreground mb-1 sm:mb-2">
          Download Ready
        </h1>
        <p className="text-sm sm:text-base text-muted-foreground">
          Your {mediaType} is ready to download
        </p>
      </div>

      <div className="bg-primary rounded-2xl p-4 sm:p-8 mb-4 sm:mb-6 relative overflow-hidden">
        <div className="absolute top-3 right-3 sm:top-4 sm:right-4">
          {mediaType === 'audio' ? (
            <Mic className="h-4 w-4 sm:h-5 sm:w-5 text-primary-foreground/60" />
          ) : (
            <Video className="h-4 w-4 sm:h-5 sm:w-5 text-primary-foreground/60" />
          )}
        </div>

        <div className="flex justify-center mb-3 sm:mb-4">
          <img src="/logo.svg" alt="AudioGrab" className="h-12 sm:h-16 w-auto" />
        </div>

        <h2 className="text-lg sm:text-2xl font-semibold text-primary-foreground text-center mb-2 sm:mb-3 line-clamp-2">
          {contentInfo.title}
        </h2>

        <div className="flex items-center justify-center gap-1.5 sm:gap-2 text-primary-foreground/70 text-xs sm:text-sm flex-wrap">
          {contentInfo.show_name && (
            <>
              <span className="truncate max-w-[120px] sm:max-w-none">{contentInfo.show_name}</span>
              <span>•</span>
            </>
          )}
          {contentInfo.creator_name && (
            <>
              <span className="truncate max-w-[100px] sm:max-w-none">{contentInfo.creator_username ? `@${contentInfo.creator_username}` : contentInfo.creator_name}</span>
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

      <div className="flex gap-2 sm:gap-3">
        <Button onClick={onReset} variant="outline" className="flex-1 h-11 sm:h-12 text-sm sm:text-base text-muted-foreground">
          <ArrowLeft className="mr-1.5 sm:mr-2 h-4 w-4 sm:h-5 sm:w-5" />
          Back
        </Button>
        <Button asChild className="flex-1 h-11 sm:h-12 text-sm sm:text-base">
          <a href={downloadUrl} download>
            <Download className="mr-1.5 sm:mr-2 h-4 w-4 sm:h-5 sm:w-5" />
            Download
          </a>
        </Button>
      </div>
    </div>
  )
}

interface TranscriptionSuccessProps {
  result: TranscriptionResult
  jobId?: string | null
  onReset: () => void
  onDownload: (renamedOutput?: string) => void
}

export function TranscriptionSuccess({
  result,
  jobId,
  onReset,
  onDownload,
}: TranscriptionSuccessProps) {
  const [copied, setCopied] = useState(false)
  const [showRenaming, setShowRenaming] = useState(false)
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({})

  // Summarization state
  const [summaryType, setSummaryType] = useState<SummaryType>('bullet_points')
  const [summary, setSummary] = useState<string | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [summaryCopied, setSummaryCopied] = useState(false)

  // Translation state
  const [languages, setLanguages] = useState<{ code: string; name: string }[]>([])
  const [targetLang, setTargetLang] = useState<string>('')
  const [translation, setTranslation] = useState<string | null>(null)
  const [translationLoading, setTranslationLoading] = useState(false)
  const [translationError, setTranslationError] = useState<string | null>(null)
  const [translationCopied, setTranslationCopied] = useState(false)
  const [translateAvailable, setTranslateAvailable] = useState(false)
  const [translatorType, setTranslatorType] = useState<'translategemma' | 'ai_provider'>('translategemma')
  const [aiProviderInfo, setAiProviderInfo] = useState<{ available: boolean; provider?: string; model?: string }>({ available: false })
  const [translateGemmaAvailable, setTranslateGemmaAvailable] = useState(false)

  // Obsidian export state
  const [obsidianConfigured, setObsidianConfigured] = useState(false)
  const [obsidianExporting, setObsidianExporting] = useState(false)
  const [obsidianResult, setObsidianResult] = useState<{
    success: boolean
    file_path?: string
    note_name?: string
    error?: string
  } | null>(null)

  // Fetch supported languages and Obsidian settings on mount
  useEffect(() => {
    fetch('/api/translate/languages')
      .then(res => res.json())
      .then(data => {
        setLanguages(data.languages || [])
      })
      .catch(() => {})

    fetch('/api/translate/available')
      .then(res => res.json())
      .then(data => {
        const gemmaAvailable = data.translategemma?.available || false
        const aiAvailable = data.ai_provider?.available || false
        setTranslateGemmaAvailable(gemmaAvailable)
        setAiProviderInfo({
          available: aiAvailable,
          provider: data.ai_provider?.provider,
          model: data.ai_provider?.model,
        })
        setTranslateAvailable(gemmaAvailable || aiAvailable)
        // Default to AI provider if available, otherwise TranslateGemma
        if (aiAvailable) {
          setTranslatorType('ai_provider')
        } else if (gemmaAvailable) {
          setTranslatorType('translategemma')
        }
      })
      .catch(() => {})

    // Check Obsidian settings
    fetch('/api/obsidian/settings')
      .then(res => res.json())
      .then(data => {
        setObsidianConfigured(data.is_configured || false)
      })
      .catch(() => {})
  }, [])

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

  const handleTranslate = async () => {
    if (!targetLang) return

    setTranslationLoading(true)
    setTranslationError(null)
    setTranslation(null)

    try {
      const response = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: result.text,
          source_lang: result.language || 'en',
          target_lang: targetLang,
          translator: translatorType,
        }),
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.detail || 'Translation failed')
      }

      const data = await response.json()
      setTranslation(data.translated_text)
    } catch (error) {
      setTranslationError(error instanceof Error ? error.message : 'Translation failed')
    } finally {
      setTranslationLoading(false)
    }
  }

  const handleCopyTranslation = async () => {
    if (!translation) return
    await navigator.clipboard.writeText(translation)
    setTranslationCopied(true)
    setTimeout(() => setTranslationCopied(false), 2000)
  }

  const handleExportToObsidian = async () => {
    if (!jobId) return

    setObsidianExporting(true)
    setObsidianResult(null)

    try {
      const response = await fetch('/api/obsidian/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: jobId,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Export failed')
      }

      setObsidianResult(data)
    } catch (error) {
      setObsidianResult({
        success: false,
        error: error instanceof Error ? error.message : 'Export failed',
      })
    } finally {
      setObsidianExporting(false)
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto px-1">
      <div className="text-center mb-5 sm:mb-8">
        <h1 className="text-xl sm:text-4xl font-bold text-foreground mb-1 sm:mb-2">
          Transcription Complete
        </h1>
        <p className="text-xs sm:text-base text-muted-foreground">
          <span className="inline-flex items-center gap-1 flex-wrap justify-center">
            <span>{result.language} ({(result.language_probability * 100).toFixed(0)}%)</span>
            <span>•</span>
            <span>{formatDuration(result.duration_seconds)}</span>
            {result.diarized && (
              <>
                <span>•</span>
                <span>{uniqueSpeakers.length} speaker{uniqueSpeakers.length !== 1 ? 's' : ''}</span>
              </>
            )}
          </span>
        </p>
      </div>

      {/* Speaker Renaming Panel */}
      {result.diarized && uniqueSpeakers.length > 0 && (
        <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 mb-3 sm:mb-4">
          <button
            onClick={() => setShowRenaming(!showRenaming)}
            className="flex items-center gap-2 w-full text-left min-h-[44px]"
          >
            <Users className="h-5 w-5 text-primary flex-shrink-0" />
            <span className="font-medium flex-1 text-sm sm:text-base">Rename Speakers</span>
            <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${showRenaming ? 'rotate-180' : ''}`} />
          </button>
          {showRenaming && (
            <div className="mt-3 sm:mt-4 space-y-3">
              {uniqueSpeakers.map(speaker => (
                <div key={speaker} className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-3">
                  <span className="text-sm text-muted-foreground sm:w-24 flex-shrink-0">{speaker}:</span>
                  <Input
                    type="text"
                    placeholder={`e.g., Host, Guest`}
                    value={speakerNames[speaker] || ''}
                    onChange={(e) => handleSpeakerRename(speaker, e.target.value)}
                    className="h-10 sm:h-8 flex-1"
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

      <div className="bg-card rounded-xl shadow-lg p-3 sm:p-6 mb-3 sm:mb-6 text-muted-foreground">
        <div className="flex items-center justify-between mb-3 sm:mb-4">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
            <span className="font-medium text-sm sm:text-base">Transcript</span>
            <span className="text-[10px] sm:text-xs text-muted-foreground uppercase">({result.output_format})</span>
          </div>
          <Button variant="outline" size="sm" onClick={handleCopy} className="h-8 w-8 sm:h-9 sm:w-9 p-0">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
        <div className="bg-muted rounded-lg p-3 sm:p-4 max-h-60 sm:max-h-80 overflow-y-auto -mx-1 sm:mx-0">
          <pre className="text-xs sm:text-sm whitespace-pre-wrap font-mono">{displayOutput}</pre>
        </div>
      </div>

      {/* Summarization Section */}
      <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 mb-3 sm:mb-6 text-muted-foreground">
        <div className="flex items-center gap-2 mb-3 sm:mb-4">
          <Sparkles className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
          <span className="font-medium text-sm sm:text-base">AI Summary</span>
        </div>

        {/* Summary Type Selector */}
        <div className="grid grid-cols-3 sm:flex sm:flex-wrap gap-1.5 sm:gap-2 mb-3 sm:mb-4">
          {SUMMARY_TYPES.map((type) => (
            <button
              key={type.value}
              onClick={() => setSummaryType(type.value)}
              disabled={summaryLoading}
              className={`px-2 sm:px-3 py-2 sm:py-1.5 rounded-lg text-xs sm:text-sm transition-all active:scale-95 ${
                summaryType === type.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              } ${summaryLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span className="hidden sm:inline">{type.label}</span>
              <span className="sm:hidden">{type.label.split(' ')[0]}</span>
            </button>
          ))}
        </div>

        {/* Generate Button */}
        <Button
          onClick={handleSummarize}
          disabled={summaryLoading}
          className="w-full mb-3 sm:mb-4 h-10 sm:h-11"
          variant={summary ? 'outline' : 'default'}
        >
          {summaryLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              <span className="text-sm">Generating...</span>
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              <span className="text-sm">{summary ? 'Regenerate' : 'Generate Summary'}</span>
            </>
          )}
        </Button>

        {/* Error Message */}
        {summaryError && (
          <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 sm:p-3 mb-3 sm:mb-4 text-xs sm:text-sm">
            {summaryError}
          </div>
        )}

        {/* Summary Result */}
        {summary && (
          <div className="space-y-2 sm:space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs sm:text-sm text-muted-foreground">
                {SUMMARY_TYPES.find(t => t.value === summaryType)?.label}
              </span>
              <Button variant="outline" size="sm" onClick={handleCopySummary} className="h-8 w-8 sm:h-9 sm:w-9 p-0">
                {summaryCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            <div className="bg-muted rounded-lg p-3 sm:p-4 max-h-48 sm:max-h-60 overflow-y-auto">
              <div className="text-xs sm:text-sm whitespace-pre-wrap prose prose-sm dark:prose-invert max-w-none">
                {summary}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Translation Section */}
      <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 mb-3 sm:mb-6 text-muted-foreground">
        <div className="flex items-center gap-2 mb-3 sm:mb-4">
          <Languages className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
          <span className="font-medium text-sm sm:text-base">Translate</span>
          {!translateAvailable && (
            <span className="text-xs text-muted-foreground">(No translator available)</span>
          )}
        </div>

        {/* Translator Type Selector */}
        {translateAvailable && (translateGemmaAvailable || aiProviderInfo.available) && (
          <div className="flex flex-wrap gap-1.5 sm:gap-2 mb-3 sm:mb-4">
            {aiProviderInfo.available && (
              <button
                onClick={() => setTranslatorType('ai_provider')}
                disabled={translationLoading}
                className={`px-2 sm:px-3 py-1.5 sm:py-1 rounded-lg text-xs sm:text-sm transition-all ${
                  translatorType === 'ai_provider'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                } ${translationLoading ? 'opacity-50' : ''}`}
              >
                AI ({aiProviderInfo.provider}/{aiProviderInfo.model?.split('/').pop()})
              </button>
            )}
            {translateGemmaAvailable && (
              <button
                onClick={() => setTranslatorType('translategemma')}
                disabled={translationLoading}
                className={`px-2 sm:px-3 py-1.5 sm:py-1 rounded-lg text-xs sm:text-sm transition-all ${
                  translatorType === 'translategemma'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                } ${translationLoading ? 'opacity-50' : ''}`}
              >
                TranslateGemma (Local)
              </button>
            )}
          </div>
        )}

        {/* Language Selector */}
        <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 mb-3 sm:mb-4">
          <div className="flex-1">
            <SearchableSelect
              value={targetLang}
              onValueChange={setTargetLang}
              options={languages.map(l => ({ value: l.code, label: l.name }))}
              placeholder="Select target language..."
              disabled={translationLoading || !translateAvailable}
            />
          </div>
          <Button
            onClick={handleTranslate}
            disabled={translationLoading || !targetLang || !translateAvailable}
            className="h-10 px-4"
            variant={translation ? 'outline' : 'default'}
          >
            {translationLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                <span className="text-sm">Translating...</span>
              </>
            ) : (
              <>
                <Languages className="mr-2 h-4 w-4" />
                <span className="text-sm">{translation ? 'Re-translate' : 'Translate'}</span>
              </>
            )}
          </Button>
        </div>

        {/* Install hint */}
        {!translateAvailable && (
          <div className="bg-muted rounded-lg p-3 text-xs sm:text-sm text-muted-foreground">
            To enable translation, either:
            <ul className="list-disc list-inside mt-1 space-y-1">
              <li>Configure an AI provider in Settings</li>
              <li>Or install TranslateGemma: <code className="bg-background px-1 py-0.5 rounded">ollama pull translategemma</code></li>
            </ul>
          </div>
        )}

        {/* Error Message */}
        {translationError && (
          <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 sm:p-3 mb-3 sm:mb-4 text-xs sm:text-sm">
            {translationError}
          </div>
        )}

        {/* Translation Result */}
        {translation && (
          <div className="space-y-2 sm:space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs sm:text-sm text-muted-foreground">
                {languages.find(l => l.code === targetLang)?.name || targetLang}
              </span>
              <Button variant="outline" size="sm" onClick={handleCopyTranslation} className="h-8 w-8 sm:h-9 sm:w-9 p-0">
                {translationCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            <div className="bg-muted rounded-lg p-3 sm:p-4 max-h-48 sm:max-h-60 overflow-y-auto">
              <div className="text-xs sm:text-sm whitespace-pre-wrap">
                {translation}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Obsidian Export Section */}
      {jobId && (
        <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 mb-3 sm:mb-6 text-muted-foreground">
          <div className="flex items-center gap-2 mb-3 sm:mb-4">
            <BookOpen className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
            <span className="font-medium text-sm sm:text-base">Export to Obsidian</span>
          </div>

          {obsidianConfigured ? (
            <>
              <Button
                onClick={handleExportToObsidian}
                disabled={obsidianExporting}
                className="w-full mb-3 h-10 sm:h-11"
                variant={obsidianResult?.success ? 'outline' : 'default'}
              >
                {obsidianExporting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    <span className="text-sm">Exporting...</span>
                  </>
                ) : (
                  <>
                    <BookOpen className="mr-2 h-4 w-4" />
                    <span className="text-sm">{obsidianResult?.success ? 'Export Again' : 'Export to Obsidian'}</span>
                  </>
                )}
              </Button>

              {/* Export Result */}
              {obsidianResult && (
                <div
                  className={`p-3 rounded-lg ${
                    obsidianResult.success
                      ? 'bg-green-500/10 border border-green-500/20'
                      : 'bg-destructive/10 border border-destructive/20'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {obsidianResult.success ? (
                      <Check className="h-4 w-4 text-green-500 flex-shrink-0 mt-0.5" />
                    ) : (
                      <ExternalLink className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-foreground text-sm">
                        {obsidianResult.success ? 'Exported successfully!' : 'Export failed'}
                      </div>
                      {obsidianResult.note_name && (
                        <div className="text-xs text-muted-foreground mt-0.5 truncate">
                          {obsidianResult.note_name}
                        </div>
                      )}
                      {obsidianResult.error && (
                        <div className="text-xs text-destructive mt-0.5">{obsidianResult.error}</div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-muted rounded-lg p-3 text-xs sm:text-sm text-muted-foreground">
              <p className="mb-2">
                Export transcriptions as markdown notes with YAML frontmatter to your Obsidian vault.
              </p>
              <Button
                variant="outline"
                size="sm"
                asChild
                className="mt-1"
              >
                <a href="/settings?tab=obsidian">
                  <Settings className="mr-2 h-3 w-3" />
                  Configure in Settings
                </a>
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Sentiment Analysis Section */}
      {jobId && result.segments && result.segments.length > 0 && (
        <SentimentSection
          jobId={jobId}
          hasSegments={result.segments.length > 0}
        />
      )}

      {/* Structured Data Extraction Section */}
      {jobId && result.text && (
        <ExtractSection
          jobId={jobId}
          hasTranscript={!!result.text}
        />
      )}

      {/* Viral Clips Hint */}
      {jobId && result.segments && result.segments.length > 0 && (
        <div className="bg-gradient-to-r from-primary/5 to-primary/10 rounded-xl p-3 sm:p-4 mb-3 sm:mb-6 text-center mt-3 sm:mt-4">
          <p className="text-sm text-muted-foreground">
            <Scissors className="inline h-4 w-4 mr-1.5 text-primary" />
            Want to create viral clips? Go to the <strong>Clips</strong> tab to generate social media clips from this transcription.
          </p>
        </div>
      )}

      <div className="flex gap-2 sm:gap-3">
        <Button onClick={onReset} variant="outline" className="flex-1 h-11 sm:h-12 text-sm sm:text-base text-muted-foreground">
          <ArrowLeft className="mr-1.5 sm:mr-2 h-4 w-4 sm:h-5 sm:w-5" />
          Back
        </Button>
        <Button onClick={handleDownload} className="flex-1 h-11 sm:h-12 text-sm sm:text-base">
          <Download className="mr-1.5 sm:mr-2 h-4 w-4 sm:h-5 sm:w-5" />
          Download
        </Button>
      </div>
    </div>
  )
}
