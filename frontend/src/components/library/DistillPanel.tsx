import { useEffect, useState } from 'react'
import { Combine, Loader2, Check, AlertTriangle, TrendingUp, Radio } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { apiGet, apiPost, errorMessage } from '@/lib/api'

interface JobRow {
  job_id: string
  job_type?: string
  status?: string
  created_at?: string
  content_info?: { title?: string; platform?: string } | null
}

interface DigestTheme {
  title: string
  summary?: string
  source_count?: number
}
interface ConsensusPoint {
  statement: string
  sources?: string[]
}
interface DisagreementPosition {
  source?: string
  stance?: string
}
interface Disagreement {
  topic: string
  positions?: DisagreementPosition[]
}
interface NotablePrediction {
  text: string
  source?: string
  horizon?: string | null
}
interface NarrativeWatch {
  narrative: string
  amplifiers?: string[]
}

interface Synthesis {
  headline?: string
  themes?: DigestTheme[]
  consensus?: ConsensusPoint[]
  disagreements?: Disagreement[]
  predictions?: NotablePrediction[]
  narratives?: NarrativeWatch[]
}

interface Distillation {
  distill_id: string
  job_ids: string[]
  mode: string
  result: Synthesis
  claim_count: number
  episode_count: number
  tokens_used: number
  model?: string | null
  created_at?: string | null
}

interface DistillResponse {
  success: boolean
  distillation?: Distillation | null
  error?: string | null
}

const MODES = [
  { value: 'synthesis', label: 'Synthesis', hint: 'What the sources agree and disagree on' },
  { value: 'debate', label: 'Debate', hint: 'Lead with the disagreements and who holds which side' },
]

function titleOf(job: JobRow): string {
  return job.content_info?.title?.trim() || job.job_id
}

export function DistillPanel() {
  const [jobs, setJobs] = useState<JobRow[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [mode, setMode] = useState('synthesis')
  const [loading, setLoading] = useState(false)
  const [loadingJobs, setLoadingJobs] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Distillation | null>(null)

  useEffect(() => {
    apiGet<{ jobs: JobRow[] }>('/api/jobs?limit=50')
      .then(data => setJobs(data.jobs.filter(j => j.status === 'completed')))
      .catch(err => setError(errorMessage(err)))
      .finally(() => setLoadingJobs(false))
  }, [])

  function toggle(jobId: string) {
    setSelected(prev =>
      prev.includes(jobId) ? prev.filter(id => id !== jobId) : [...prev, jobId],
    )
  }

  async function distill() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await apiPost<DistillResponse>('/api/distill', {
        job_ids: selected,
        mode,
      })
      if (!data.success || !data.distillation) {
        setError(data.error || 'Distillation failed.')
        return
      }
      setResult(data.distillation)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const synthesis = result?.result
  const enough = selected.length >= 2

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Pick two or more episodes and get one brief: what they agreed on, where they
        contradict each other, and which narratives repeat across sources.
      </p>

      {loadingJobs ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading episodes…
        </div>
      ) : jobs.length === 0 ? (
        <p className="text-sm text-muted-foreground py-6 text-center">
          No completed episodes yet. Transcribe a couple first.
        </p>
      ) : (
        <div className="border border-border rounded-lg divide-y divide-border max-h-64 overflow-y-auto">
          {jobs.map(job => {
            const checked = selected.includes(job.job_id)
            return (
              <label
                key={job.job_id}
                className="flex items-center gap-3 p-2.5 cursor-pointer hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(job.job_id)}
                  className="shrink-0 h-4 w-4 accent-current"
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-xs sm:text-sm truncate">{titleOf(job)}</span>
                  {job.content_info?.platform && (
                    <span className="block text-[11px] text-muted-foreground">
                      {job.content_info.platform}
                    </span>
                  )}
                </span>
              </label>
            )
          })}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
        <div className="flex-1">
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">Mode</label>
          <select
            value={mode}
            onChange={e => setMode(e.target.value)}
            disabled={loading}
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {MODES.map(m => (
              <option key={m.value} value={m.value}>
                {m.label} — {m.hint}
              </option>
            ))}
          </select>
        </div>
        <Button onClick={distill} disabled={loading || !enough} className="shrink-0">
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Distilling…
            </>
          ) : (
            <>
              <Combine className="mr-2 h-4 w-4" />
              Distill {selected.length > 0 ? `${selected.length} episodes` : ''}
            </>
          )}
        </Button>
      </div>

      {!enough && selected.length > 0 && (
        <p className="text-xs text-muted-foreground">Select at least one more episode.</p>
      )}

      {error && (
        <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 sm:p-3 text-xs sm:text-sm">
          {error}
        </div>
      )}

      {synthesis && (
        <div className="space-y-4">
          {synthesis.headline && (
            <div className="bg-primary/10 rounded-lg p-3">
              <h3 className="text-sm font-semibold">{synthesis.headline}</h3>
              <p className="text-[11px] text-muted-foreground mt-1">
                {result!.episode_count} episodes · {result!.claim_count} claims
                {result!.model ? ` · ${result!.model}` : ''}
              </p>
            </div>
          )}

          {!!synthesis.themes?.length && (
            <Group icon={<Combine className="h-3.5 w-3.5" />} title="Themes">
              {synthesis.themes.map((t, i) => (
                <div key={i} className="bg-muted rounded-lg p-3">
                  <h4 className="text-xs font-semibold">{t.title}</h4>
                  {t.summary && <p className="text-xs mt-1 leading-relaxed">{t.summary}</p>}
                  {!!t.source_count && (
                    <p className="text-[11px] text-muted-foreground mt-1">
                      {t.source_count} source{t.source_count === 1 ? '' : 's'}
                    </p>
                  )}
                </div>
              ))}
            </Group>
          )}

          {!!synthesis.consensus?.length && (
            <Group icon={<Check className="h-3.5 w-3.5" />} title="Agreed on">
              {synthesis.consensus.map((c, i) => (
                <div key={i} className="bg-muted rounded-lg p-3">
                  <p className="text-xs leading-relaxed">{c.statement}</p>
                  {!!c.sources?.length && (
                    <p className="text-[11px] text-muted-foreground mt-1">
                      {c.sources.join(' · ')}
                    </p>
                  )}
                </div>
              ))}
            </Group>
          )}

          {!!synthesis.disagreements?.length && (
            <Group icon={<AlertTriangle className="h-3.5 w-3.5" />} title="Disagreed on">
              {synthesis.disagreements.map((d, i) => (
                <div key={i} className="bg-muted rounded-lg p-3">
                  <h4 className="text-xs font-semibold mb-1.5">{d.topic}</h4>
                  <div className="space-y-1.5">
                    {d.positions?.map((p, pi) => (
                      <div key={pi} className="border-l-2 border-primary/40 pl-2">
                        {p.source && (
                          <span className="text-[11px] font-medium text-muted-foreground">
                            {p.source}
                          </span>
                        )}
                        <p className="text-xs leading-relaxed">{p.stance}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </Group>
          )}

          {!!synthesis.predictions?.length && (
            <Group icon={<TrendingUp className="h-3.5 w-3.5" />} title="Predictions">
              {synthesis.predictions.map((p, i) => (
                <div key={i} className="bg-muted rounded-lg p-3">
                  <p className="text-xs leading-relaxed">{p.text}</p>
                  <p className="text-[11px] text-muted-foreground mt-1">
                    {[p.source, p.horizon].filter(Boolean).join(' · ')}
                  </p>
                </div>
              ))}
            </Group>
          )}

          {!!synthesis.narratives?.length && (
            <Group icon={<Radio className="h-3.5 w-3.5" />} title="Repeated narratives">
              {synthesis.narratives.map((n, i) => (
                <div key={i} className="bg-muted rounded-lg p-3">
                  <p className="text-xs leading-relaxed">{n.narrative}</p>
                  {!!n.amplifiers?.length && (
                    <p className="text-[11px] text-muted-foreground mt-1">
                      Amplified by {n.amplifiers.join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </Group>
          )}
        </div>
      )}
    </div>
  )
}

function Group({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  )
}
