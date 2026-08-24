import { useEffect, useState } from 'react'
import { Check, Loader2, X, Circle, Workflow, ChevronDown } from 'lucide-react'
import { apiGet } from '@/lib/api'

interface StageState {
  name: string
  status: string
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
  detail?: Record<string, unknown> | null
}

interface PipelineStatus {
  job_id: string
  profile: string
  job_status: string
  knowledge_status?: string | null
  started_at?: string | null
  completed_at?: string | null
  stages: StageState[]
}

const POLL_MS = 2000
const TERMINAL = new Set(['completed', 'failed', 'cancelled'])

const STAGE_LABELS: Record<string, string> = {
  download: 'Download',
  transcribe: 'Transcribe',
  search_index: 'Index for search',
  knowledge: 'Extract knowledge',
  summary: 'Summarize',
  sentiment: 'Analyze sentiment',
  clips: 'Find clips',
  webhook: 'Notify',
  notify: 'Notify',
}

function label(name: string): string {
  return STAGE_LABELS[name] ?? name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function StageIcon({ status }: { status: string }) {
  if (status === 'completed') return <Check className="h-3.5 w-3.5 text-primary" />
  if (status === 'running') return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
  if (status === 'failed') return <X className="h-3.5 w-3.5 text-destructive" />
  if (status === 'skipped') return <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />
  return <Circle className="h-3.5 w-3.5 text-muted-foreground/40" />
}

function elapsed(stage: StageState): string {
  if (!stage.started_at || !stage.completed_at) return ''
  const ms = Date.parse(stage.completed_at) - Date.parse(stage.started_at)
  if (!Number.isFinite(ms) || ms < 0) return ''
  return ms < 1000 ? '<1s' : `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)}s`
}

interface PipelineProgressProps {
  jobId: string
}

export function PipelineProgress({ jobId }: PipelineProgressProps) {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [expanded, setExpanded] = useState(true)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const data = await apiGet<PipelineStatus>(`/api/jobs/${jobId}/pipeline`)
        if (cancelled) return
        setStatus(data)
        // Stop polling once nothing can change again.
        const done =
          TERMINAL.has(data.job_status) &&
          data.stages.every(s => TERMINAL.has(s.status) || s.status === 'skipped')
        if (!done) timer = setTimeout(poll, POLL_MS)
      } catch {
        // A job that never ran through the agentic pipeline has no stages;
        // that is not an error, there is just nothing to show.
        if (!cancelled) setMissing(true)
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [jobId])

  if (missing || !status || status.stages.length === 0) return null

  const done = status.stages.filter(s => s.status === 'completed').length
  const failed = status.stages.find(s => s.status === 'failed')

  return (
    <div className="border border-border rounded-lg p-3 mb-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left min-h-[36px]"
      >
        <Workflow className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs sm:text-sm font-medium flex-1">
          Pipeline
          <span className="ml-1.5 text-muted-foreground font-normal">
            {status.profile} · {done}/{status.stages.length}
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {expanded && (
        <ol className="mt-3 space-y-1.5">
          {status.stages.map(stage => (
            <li key={stage.name} className="flex items-start gap-2.5">
              <span className="mt-0.5 shrink-0">
                <StageIcon status={stage.status} />
              </span>
              <span className="min-w-0 flex-1">
                <span
                  className={`text-xs ${
                    stage.status === 'pending' || stage.status === 'skipped'
                      ? 'text-muted-foreground'
                      : ''
                  }`}
                >
                  {label(stage.name)}
                </span>
                {stage.status === 'skipped' && (
                  <span className="ml-1.5 text-[11px] text-muted-foreground">skipped</span>
                )}
                {stage.error && (
                  <span className="block text-[11px] text-destructive mt-0.5">{stage.error}</span>
                )}
              </span>
              <span className="shrink-0 text-[11px] text-muted-foreground tabular-nums">
                {elapsed(stage)}
              </span>
            </li>
          ))}
        </ol>
      )}

      {failed && !expanded && (
        <p className="mt-2 text-[11px] text-destructive">{label(failed.name)} failed</p>
      )}
    </div>
  )
}
