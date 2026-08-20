import { useEffect, useRef, useState } from 'react'
import { Search, Loader2, ExternalLink, Database } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { apiGet, apiPost, errorMessage, formatTimestamp, sourceLinkAt } from '@/lib/api'

interface SearchHit {
  job_id: string
  chunk_id: string
  text: string
  start_s?: number | null
  end_s?: number | null
  speaker?: string | null
  score: number
  title?: string | null
  source_url?: string | null
  platform?: string | null
}

interface SearchResponse {
  query: string
  count: number
  results: SearchHit[]
}

interface SearchStatus {
  chunk_count: number
  indexed_jobs: number
  unindexed_jobs: number
}

export function SearchPanel() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchHit[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<SearchStatus | null>(null)
  const [indexing, setIndexing] = useState(false)
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => {
    apiGet<SearchStatus>('/api/search/status')
      .then(setStatus)
      .catch(() => setStatus(null))
    return () => inFlight.current?.abort()
  }, [])

  async function runSearch(e?: React.FormEvent) {
    e?.preventDefault()
    const q = query.trim()
    if (!q) return

    // A fast typist can outrun the embedding call; drop the stale one.
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller

    setLoading(true)
    setError(null)
    try {
      const data = await apiPost<SearchResponse>('/api/search', { query: q, k: 20 }, controller.signal)
      setResults(data.results)
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') return
      setError(errorMessage(err))
      setResults(null)
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  async function reindex() {
    setIndexing(true)
    setError(null)
    try {
      await apiPost('/api/search/reindex?limit=100')
      setStatus(await apiGet<SearchStatus>('/api/search/status'))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setIndexing(false)
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={runSearch} className="flex gap-2">
        <Input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search your library by meaning, not keywords…"
          className="flex-1"
          aria-label="Search query"
        />
        <Button type="submit" disabled={loading || !query.trim()} className="shrink-0">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          <span className="hidden sm:inline">Search</span>
        </Button>
      </form>

      {status && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Database className="h-3.5 w-3.5" />
          <span>
            {status.chunk_count.toLocaleString()} segments from{' '}
            {status.indexed_jobs.toLocaleString()} episodes
          </span>
          {status.unindexed_jobs > 0 && (
            <>
              <span className="text-muted-foreground/60">·</span>
              <span>{status.unindexed_jobs} not indexed</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs"
                onClick={reindex}
                disabled={indexing}
              >
                {indexing ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
                Index them
              </Button>
            </>
          )}
        </div>
      )}

      {error && (
        <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 sm:p-3 text-xs sm:text-sm">
          {error}
        </div>
      )}

      {results && results.length === 0 && !loading && (
        <p className="text-sm text-muted-foreground py-6 text-center">
          Nothing matched. Try describing the idea rather than the exact words.
        </p>
      )}

      {results && results.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">{results.length} results</p>
          {results.map(hit => {
            const link = sourceLinkAt(hit.source_url, hit.start_s)
            return (
              <article key={hit.chunk_id} className="bg-muted rounded-lg p-3">
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="min-w-0">
                    <h3 className="text-xs font-semibold truncate">
                      {hit.title || hit.job_id}
                    </h3>
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                      {hit.platform && <span>{hit.platform}</span>}
                      {hit.speaker && <span>· {hit.speaker}</span>}
                      {hit.start_s !== null && hit.start_s !== undefined && (
                        <span>· {formatTimestamp(hit.start_s)}</span>
                      )}
                    </div>
                  </div>
                  <span
                    className="shrink-0 px-2 py-0.5 rounded-full text-[11px] font-medium bg-primary/20 text-primary"
                    title="Similarity score"
                  >
                    {hit.score.toFixed(2)}
                  </span>
                </div>
                <p className="text-xs sm:text-sm leading-relaxed">{hit.text}</p>
                {link && (
                  <a
                    href={link}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 mt-2 text-[11px] text-primary hover:underline"
                  >
                    Open at {formatTimestamp(hit.start_s) || 'source'}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
