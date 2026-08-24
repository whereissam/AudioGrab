import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Loader2, Send, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { apiGet, apiPost, errorMessage, formatTimestamp, sourceLinkAt } from '@/lib/api'

interface RAGSource {
  job_id?: string
  chunk_id?: string
  text?: string
  start_s?: number | null
  end_s?: number | null
  speaker?: string | null
  score?: number
  title?: string | null
  source_url?: string | null
}

interface AskResponse {
  success: boolean
  question: string
  answer?: string | null
  sources: RAGSource[]
  retrieved_count: number
  tokens_used: number
  model?: string | null
  error?: string | null
}

interface HistoryEntry {
  id: number
  job_id?: string | null
  question: string
  answer: string
  sources: RAGSource[]
  model?: string | null
  created_at: string
}

interface Turn {
  question: string
  answer: string
  sources: RAGSource[]
  model?: string | null
}

interface AskPanelProps {
  /** Scope to one episode; omit to ask the whole library. */
  jobId?: string
}

export function AskPanel({ jobId }: AskPanelProps) {
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const askPath = jobId ? `/api/jobs/${jobId}/ask` : '/api/ask'
  const historyPath = jobId ? `/api/jobs/${jobId}/chat-history` : '/api/ask/history'

  useEffect(() => {
    let cancelled = false
    apiGet<{ history: HistoryEntry[] }>(historyPath)
      .then(data => {
        if (cancelled) return
        // History comes back newest-first; a transcript reads oldest-first.
        setTurns(
          [...data.history].reverse().map(h => ({
            question: h.question,
            answer: h.answer,
            sources: h.sources ?? [],
            model: h.model,
          })),
        )
      })
      .catch(() => {
        /* no history yet is not an error worth showing */
      })
    return () => {
      cancelled = true
    }
  }, [historyPath])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length, loading])

  async function ask(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || loading) return

    setLoading(true)
    setError(null)
    setQuestion('')
    try {
      const data = await apiPost<AskResponse>(askPath, { question: q })
      if (!data.success || !data.answer) {
        setError(data.error || 'No answer came back for that question.')
        setQuestion(q) // let them retry without retyping
        return
      }
      setTurns(prev => [
        ...prev,
        { question: q, answer: data.answer!, sources: data.sources ?? [], model: data.model },
      ])
    } catch (err) {
      setError(errorMessage(err))
      setQuestion(q)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-4 min-h-[120px]">
        {turns.length === 0 && !loading && (
          <div className="text-center py-8">
            <MessageSquare className="h-6 w-6 mx-auto mb-2 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {jobId
                ? 'Ask anything about this episode.'
                : 'Ask a question and get an answer grounded in your library.'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Answers cite the transcript segments they came from.
            </p>
          </div>
        )}

        {turns.map((turn, i) => (
          <div key={i} className="space-y-2">
            <div className="flex justify-end">
              <p className="bg-primary/15 text-foreground rounded-lg px-3 py-2 text-sm max-w-[85%]">
                {turn.question}
              </p>
            </div>
            <div className="bg-muted rounded-lg p-3">
              <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">{turn.answer}</p>

              {turn.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border space-y-1.5">
                  <p className="text-[11px] font-medium text-muted-foreground">
                    {turn.sources.length} source{turn.sources.length === 1 ? '' : 's'}
                  </p>
                  {turn.sources.map((s, si) => {
                    const link = sourceLinkAt(s.source_url, s.start_s)
                    return (
                      <div key={si} className="text-[11px] text-muted-foreground">
                        <span className="font-medium text-foreground">
                          {s.title || s.job_id || 'Source'}
                        </span>
                        {s.start_s !== null && s.start_s !== undefined && (
                          <> · {formatTimestamp(s.start_s)}</>
                        )}
                        {s.speaker && <> · {s.speaker}</>}
                        {link && (
                          <a
                            href={link}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-0.5 ml-1.5 text-primary hover:underline"
                          >
                            open
                            <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {turn.model && (
                <p className="mt-2 text-[11px] text-muted-foreground/70">{turn.model}</p>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="bg-muted rounded-lg p-3 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Searching the transcript and drafting an answer…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 sm:p-3 text-xs sm:text-sm">
          {error}
        </div>
      )}

      <form onSubmit={ask} className="flex gap-2">
        <Input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder={jobId ? 'Ask about this episode…' : 'Ask your library…'}
          className="flex-1"
          disabled={loading}
          aria-label="Question"
        />
        <Button type="submit" disabled={loading || !question.trim()} className="shrink-0">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          <span className="hidden sm:inline">Ask</span>
        </Button>
      </form>
    </div>
  )
}
