import { useEffect, useState } from 'react'
import { GitCompareArrows, Loader2, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { apiGet, apiPost, errorMessage, formatTimestamp } from '@/lib/api'

interface ClaimRef {
  claim_id: string
  episode_id?: string | null
  text?: string | null
  speaker?: string | null
  timestamp_start?: number | null
  timestamp_end?: number | null
}

interface Contradiction {
  contradiction_id: string
  speaker?: string | null
  explanation?: string | null
  confidence?: number | null
  detected_at?: string | null
  claim_a: ClaimRef
  claim_b: ClaimRef
}

interface ListResponse {
  count: number
  contradictions: Contradiction[]
}

interface AnalyzeResponse {
  success: boolean
  scope: string
  pairs_considered: number
  pairs_judged: number
  contradiction_count: number
  contradictions: Contradiction[]
  tokens_used: number
  model?: string | null
  error?: string | null
}

interface ContradictionSectionProps {
  jobId: string
  hasTranscript: boolean
}

function ClaimCard({ claim, side }: { claim: ClaimRef; side: 'A' | 'B' }) {
  return (
    <div className="bg-background/60 rounded-lg p-2.5">
      <div className="flex items-center gap-1.5 mb-1">
        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/20 text-primary">
          {side}
        </span>
        {claim.speaker && (
          <span className="text-[11px] text-muted-foreground">{claim.speaker}</span>
        )}
        {claim.timestamp_start !== null && claim.timestamp_start !== undefined && (
          <span className="text-[11px] text-muted-foreground">
            · {formatTimestamp(claim.timestamp_start)}
          </span>
        )}
      </div>
      <p className="text-xs leading-relaxed">{claim.text || claim.claim_id}</p>
    </div>
  )
}

export function ContradictionSection({ jobId, hasTranscript }: ContradictionSectionProps) {
  const [contradictions, setContradictions] = useState<Contradiction[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [lastRun, setLastRun] = useState<AnalyzeResponse | null>(null)

  useEffect(() => {
    let cancelled = false
    apiGet<ListResponse>(`/api/jobs/${jobId}/contradictions`)
      .then(data => {
        if (cancelled) return
        setContradictions(data.contradictions)
        if (data.contradictions.length > 0) setExpanded(true)
      })
      .catch(() => {
        /* nothing analyzed yet */
      })
    return () => {
      cancelled = true
    }
  }, [jobId])

  async function analyze() {
    setLoading(true)
    setError(null)
    try {
      const data = await apiPost<AnalyzeResponse>(`/api/jobs/${jobId}/analyze-contradictions`)
      if (!data.success) {
        setError(data.error || 'Contradiction analysis failed.')
        return
      }
      setLastRun(data)
      setContradictions(data.contradictions)
      setExpanded(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (!hasTranscript) return null

  const found = contradictions?.length ?? 0

  return (
    <div className="border border-border rounded-lg p-3 mb-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left min-h-[36px]"
      >
        <GitCompareArrows className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs sm:text-sm font-medium flex-1">
          Contradictions
          {contradictions !== null && (
            <span className="ml-1.5 text-muted-foreground font-normal">
              {found === 0 ? 'none found' : found}
            </span>
          )}
        </span>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {expanded && (
        <div className="mt-3 space-y-3">
          <p className="text-xs text-muted-foreground">
            Cross-references the claims extracted from this episode and surfaces pairs that
            can't both be true.
          </p>

          {error && (
            <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 text-xs">
              {error}
            </div>
          )}

          {found > 0 && (
            <div className="space-y-3">
              {contradictions!.map(c => (
                <article key={c.contradiction_id} className="bg-muted rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                      {c.speaker && (
                        <h4 className="text-xs font-semibold truncate">{c.speaker}</h4>
                      )}
                      {c.explanation && (
                        <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">
                          {c.explanation}
                        </p>
                      )}
                    </div>
                    {c.confidence !== null && c.confidence !== undefined && (
                      <span
                        className="shrink-0 px-2 py-0.5 rounded-full text-[11px] font-medium bg-primary/20 text-primary"
                        title="Detector confidence"
                      >
                        {c.confidence.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <div className="space-y-2">
                    <ClaimCard claim={c.claim_a} side="A" />
                    <ClaimCard claim={c.claim_b} side="B" />
                  </div>
                </article>
              ))}
            </div>
          )}

          {contradictions !== null && found === 0 && !loading && (
            <p className="text-xs text-muted-foreground">
              No contradictions found in this episode.
              {lastRun ? ` ${lastRun.pairs_judged} claim pairs checked.` : ''}
            </p>
          )}

          <Button
            onClick={analyze}
            disabled={loading}
            variant="outline"
            className="w-full h-9"
            size="sm"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                <span className="text-xs">Checking claims…</span>
              </>
            ) : (
              <>
                <GitCompareArrows className="mr-2 h-3 w-3" />
                <span className="text-xs">
                  {contradictions === null ? 'Find contradictions' : 'Re-analyze'}
                </span>
              </>
            )}
          </Button>

          {lastRun?.model && (
            <p className="text-[11px] text-muted-foreground/70">
              {lastRun.pairs_considered} pairs considered · {lastRun.model}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
