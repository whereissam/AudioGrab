import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { RefreshCw, Loader2, Clock, ArrowUp, ArrowDown, Trash2, Play } from 'lucide-react'

interface QueueJob {
  job_id: string
  priority: number
  queued_at: string
}

interface QueueStatus {
  pending: number
  processing: number
  max_concurrent: number
  processing_jobs: string[]
  jobs: QueueJob[]
}

const PRIORITY_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: 'Low', color: 'text-muted-foreground' },
  2: { label: 'Low', color: 'text-muted-foreground' },
  3: { label: 'Low', color: 'text-muted-foreground' },
  4: { label: 'Normal', color: 'text-foreground' },
  5: { label: 'Normal', color: 'text-foreground' },
  6: { label: 'Normal', color: 'text-foreground' },
  7: { label: 'High', color: 'text-orange-500' },
  8: { label: 'High', color: 'text-orange-500' },
  9: { label: 'Urgent', color: 'text-destructive' },
  10: { label: 'Urgent', color: 'text-destructive' },
}

export function QueueView() {
  const [queue, setQueue] = useState<QueueStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatingJob, setUpdatingJob] = useState<string | null>(null)

  const fetchQueue = async () => {
    try {
      const response = await fetch('/api/queue')
      if (!response.ok) throw new Error('Failed to fetch queue')
      const data = await response.json()
      setQueue(data)
      setError(null)
    } catch {
      setError('Failed to load queue status')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchQueue()
    const interval = setInterval(fetchQueue, 5000)
    return () => clearInterval(interval)
  }, [])

  const updatePriority = async (jobId: string, newPriority: number) => {
    setUpdatingJob(jobId)
    try {
      const response = await fetch(`/api/download/${jobId}/priority?priority=${newPriority}`, {
        method: 'PATCH',
      })
      if (!response.ok) throw new Error('Failed to update priority')
      await fetchQueue()
    } catch {
      setError('Failed to update priority')
    } finally {
      setUpdatingJob(null)
    }
  }

  const cancelJob = async (jobId: string) => {
    if (!confirm('Cancel this download?')) return

    setUpdatingJob(jobId)
    try {
      const response = await fetch(`/api/download/${jobId}`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error('Failed to cancel job')
      await fetchQueue()
    } catch {
      setError('Failed to cancel job')
    } finally {
      setUpdatingJob(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Download Queue</h2>
        <Button variant="outline" size="sm" onClick={fetchQueue}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive p-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {queue && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-muted rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-primary">{queue.pending}</div>
              <div className="text-xs text-muted-foreground">Pending</div>
            </div>
            <div className="bg-muted rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-orange-500">{queue.processing}</div>
              <div className="text-xs text-muted-foreground">Processing</div>
            </div>
            <div className="bg-muted rounded-lg p-3 text-center">
              <div className="text-2xl font-bold">{queue.max_concurrent}</div>
              <div className="text-xs text-muted-foreground">Max Concurrent</div>
            </div>
          </div>

          {/* Processing Jobs */}
          {queue.processing_jobs.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium flex items-center gap-2">
                <Play className="h-4 w-4 text-primary" />
                Currently Processing
              </h3>
              <div className="space-y-1">
                {queue.processing_jobs.map((jobId) => (
                  <div
                    key={jobId}
                    className="flex items-center gap-2 p-2 bg-primary/5 rounded-lg border border-primary/20"
                  >
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="font-mono text-xs truncate flex-1">{jobId}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Queue */}
          <div className="space-y-2">
            <h3 className="text-sm font-medium flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Queued Jobs ({queue.jobs.length})
            </h3>

            {queue.jobs.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No jobs in queue
              </div>
            ) : (
              <div className="space-y-2">
                {queue.jobs.map((job, index) => {
                  const priorityInfo = PRIORITY_LABELS[job.priority] || PRIORITY_LABELS[5]
                  const isUpdating = updatingJob === job.job_id

                  return (
                    <div
                      key={job.job_id}
                      className="flex items-center gap-3 p-3 bg-card border rounded-lg"
                    >
                      <div className="text-sm font-medium text-muted-foreground w-6">
                        #{index + 1}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="font-mono text-xs truncate">{job.job_id}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <span
                            className={`text-xs font-medium px-2 py-0.5 rounded ${priorityInfo.color} bg-current/10`}
                          >
                            {priorityInfo.label} ({job.priority})
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {new Date(job.queued_at).toLocaleTimeString()}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => updatePriority(job.job_id, Math.min(10, job.priority + 1))}
                          disabled={isUpdating || job.priority >= 10}
                          className="h-8 w-8 p-0"
                          title="Increase priority"
                        >
                          {isUpdating ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <ArrowUp className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => updatePriority(job.job_id, Math.max(1, job.priority - 1))}
                          disabled={isUpdating || job.priority <= 1}
                          className="h-8 w-8 p-0"
                          title="Decrease priority"
                        >
                          <ArrowDown className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => cancelJob(job.job_id)}
                          disabled={isUpdating}
                          className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                          title="Cancel"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
