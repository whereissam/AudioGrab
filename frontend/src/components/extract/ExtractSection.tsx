import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { FileText, Loader2, ChevronDown, Copy, Check } from 'lucide-react'

interface ExtractedField {
  key: string
  value: unknown
  field_type: string
}

interface ExtractionData {
  success: boolean
  job_id: string
  preset?: string
  fields: ExtractedField[]
  raw_output?: string
  model?: string
  provider?: string
  tokens_used?: number
  error?: string
}

interface PresetInfo {
  name: string
  value: string
  description: string
  example_fields: string[]
}

interface ExtractSectionProps {
  jobId: string
  hasTranscript: boolean
}

const BUILT_IN_PRESETS: PresetInfo[] = [
  {
    name: 'Meeting Notes',
    value: 'meeting_notes',
    description: 'Extract attendees, agenda items, decisions, action items, and key quotes',
    example_fields: ['attendees', 'agenda_items', 'decisions', 'action_items', 'key_quotes'],
  },
  {
    name: 'Interview',
    value: 'interview',
    description: 'Extract interviewer/interviewee, Q&A pairs, key quotes, and topics',
    example_fields: ['interviewer', 'interviewee', 'questions', 'key_quotes', 'topics_discussed'],
  },
  {
    name: 'Tutorial',
    value: 'tutorial',
    description: 'Extract title, prerequisites, step-by-step instructions, tools, and links',
    example_fields: ['title', 'prerequisites', 'steps', 'tools_mentioned', 'links_mentioned'],
  },
  {
    name: 'News / Analysis',
    value: 'news_analysis',
    description: 'Extract claims with evidence, predictions, entities, and key takeaways',
    example_fields: ['claims', 'predictions', 'entities', 'key_takeaways'],
  },
  {
    name: 'Product Review',
    value: 'product_review',
    description: 'Extract product name, rating, pros, cons, comparisons, and verdict',
    example_fields: ['product_name', 'overall_rating', 'pros', 'cons', 'comparisons', 'verdict'],
  },
]

function formatFieldKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

function renderFieldValue(value: unknown, fieldType: string): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground italic">N/A</span>
  }

  if (fieldType === 'list' && Array.isArray(value)) {
    return (
      <ul className="list-disc list-inside space-y-0.5">
        {(value as string[]).map((item, i) => (
          <li key={i} className="text-xs sm:text-sm">{String(item)}</li>
        ))}
      </ul>
    )
  }

  if (fieldType === 'object_list' && Array.isArray(value)) {
    return (
      <div className="space-y-2">
        {(value as Record<string, unknown>[]).map((item, i) => (
          <div key={i} className="bg-background/50 rounded-lg p-2 text-xs sm:text-sm">
            {Object.entries(item).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="font-medium text-muted-foreground min-w-[80px]">{formatFieldKey(k)}:</span>
                <span>{v !== null && v !== undefined ? String(v) : 'N/A'}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }

  if (fieldType === 'object' && typeof value === 'object') {
    return (
      <div className="bg-background/50 rounded-lg p-2 text-xs sm:text-sm">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <span className="font-medium text-muted-foreground min-w-[80px]">{formatFieldKey(k)}:</span>
            <span>{v !== null && v !== undefined ? String(v) : 'N/A'}</span>
          </div>
        ))}
      </div>
    )
  }

  return <span className="text-xs sm:text-sm">{String(value)}</span>
}

export function ExtractSection({ jobId, hasTranscript }: ExtractSectionProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<ExtractionData | null>(null)
  const [available, setAvailable] = useState<boolean | null>(null)
  const [unavailableReason, setUnavailableReason] = useState<string | null>(null)
  const [selectedPreset, setSelectedPreset] = useState(BUILT_IN_PRESETS[0].value)
  const [showRawOutput, setShowRawOutput] = useState(false)
  const [copiedJson, setCopiedJson] = useState(false)

  // Check availability on mount
  useEffect(() => {
    if (!jobId) return

    fetch(`/api/jobs/${jobId}/extract/available`)
      .then(res => res.json())
      .then(data => {
        setAvailable(data.available)
        setUnavailableReason(data.reason || null)
      })
      .catch(() => {
        setAvailable(false)
        setUnavailableReason('Failed to check availability')
      })

    // Try to load cached results
    fetch(`/api/jobs/${jobId}/extract`)
      .then(res => {
        if (res.ok) return res.json()
        return null
      })
      .then(data => {
        if (data && data.success) {
          setData(data)
        }
      })
      .catch(() => {})
  }, [jobId])

  const handleExtract = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/jobs/${jobId}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset: selectedPreset }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Extraction failed')
      }

      const result = await response.json()
      if (result.success) {
        setData(result)
      } else {
        setError(result.error || 'Extraction failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCopyJson = async () => {
    if (!data?.raw_output) return
    try {
      await navigator.clipboard.writeText(data.raw_output)
      setCopiedJson(true)
      setTimeout(() => setCopiedJson(false), 2000)
    } catch {
      // Clipboard API may fail in some contexts
    }
  }

  // Not available
  if (available !== null && available === false) {
    return (
      <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 text-muted-foreground">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
          <span className="font-medium text-sm sm:text-base">Structured Data Extraction</span>
        </div>
        <div className="bg-muted rounded-lg p-3 text-xs sm:text-sm">
          {unavailableReason || 'Structured extraction is not available for this transcription.'}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 text-muted-foreground">
      <div className="flex items-center gap-2 mb-3 sm:mb-4">
        <FileText className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
        <span className="font-medium text-sm sm:text-base">Structured Data Extraction</span>
      </div>

      {/* Preset selector and extract button */}
      {!data && (
        <div className="space-y-3 mb-3 sm:mb-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Extraction Preset
            </label>
            <select
              value={selectedPreset}
              onChange={e => setSelectedPreset(e.target.value)}
              disabled={loading}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {BUILT_IN_PRESETS.map(preset => (
                <option key={preset.value} value={preset.value}>
                  {preset.name} — {preset.description}
                </option>
              ))}
            </select>
          </div>
          <Button
            onClick={handleExtract}
            disabled={loading || !hasTranscript || !available}
            className="w-full h-10 sm:h-11"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                <span className="text-sm">Extracting data...</span>
              </>
            ) : (
              <>
                <FileText className="mr-2 h-4 w-4" />
                <span className="text-sm">Extract Structured Data</span>
              </>
            )}
          </Button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 sm:p-3 mb-3 sm:mb-4 text-xs sm:text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {data && data.success && (
        <div className="space-y-4">
          {/* Preset badge */}
          {data.preset && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2 py-1 rounded-full text-xs font-medium bg-primary/20 text-primary">
                {BUILT_IN_PRESETS.find(p => p.value === data.preset)?.name || data.preset}
              </span>
              {data.tokens_used && (
                <span className="text-xs text-muted-foreground">
                  {data.tokens_used.toLocaleString()} tokens
                </span>
              )}
            </div>
          )}

          {/* Extracted fields as cards */}
          <div className="space-y-3">
            {data.fields.map((field, idx) => (
              <div key={idx} className="bg-muted rounded-lg p-3">
                <h4 className="text-xs font-semibold text-foreground mb-1.5">
                  {formatFieldKey(field.key)}
                </h4>
                {renderFieldValue(field.value, field.field_type)}
              </div>
            ))}
          </div>

          {/* Raw JSON output */}
          {data.raw_output && (
            <div>
              <button
                onClick={() => setShowRawOutput(!showRawOutput)}
                className="flex items-center gap-2 w-full text-left min-h-[36px]"
              >
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs sm:text-sm font-medium flex-1">
                  Raw JSON Output
                </span>
                <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${showRawOutput ? 'rotate-180' : ''}`} />
              </button>

              {showRawOutput && (
                <div className="mt-2">
                  <div className="flex justify-end mb-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCopyJson}
                      className="h-7 text-xs"
                    >
                      {copiedJson ? (
                        <>
                          <Check className="mr-1 h-3 w-3" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="mr-1 h-3 w-3" />
                          Copy JSON
                        </>
                      )}
                    </Button>
                  </div>
                  <pre className="bg-muted rounded-lg p-3 text-xs overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap">
                    {data.raw_output}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Re-extract button */}
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                Extraction Preset
              </label>
              <select
                value={selectedPreset}
                onChange={e => setSelectedPreset(e.target.value)}
                disabled={loading}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {BUILT_IN_PRESETS.map(preset => (
                  <option key={preset.value} value={preset.value}>
                    {preset.name} — {preset.description}
                  </option>
                ))}
              </select>
            </div>
            <Button
              onClick={handleExtract}
              disabled={loading}
              variant="outline"
              className="w-full h-9"
              size="sm"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  <span className="text-xs">Re-extracting...</span>
                </>
              ) : (
                <>
                  <FileText className="mr-2 h-3 w-3" />
                  <span className="text-xs">Re-extract</span>
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
