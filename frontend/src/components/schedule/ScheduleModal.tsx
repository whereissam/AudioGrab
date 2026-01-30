import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Calendar, Clock, Loader2, Trash2, AlertCircle, Check, X } from 'lucide-react'

interface ScheduledJob {
  job_id: string
  url: string
  scheduled_at: string
  priority: number
  status: string
  created_at: string
}

interface ScheduleModalProps {
  isOpen: boolean
  onClose: () => void
  onScheduled?: () => void
}

export function ScheduleModal({ isOpen, onClose, onScheduled }: ScheduleModalProps) {
  const [url, setUrl] = useState('')
  const [scheduledDate, setScheduledDate] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')
  const [priority, setPriority] = useState(5)
  const [format, setFormat] = useState('m4a')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const [scheduledJobs, setScheduledJobs] = useState<ScheduledJob[]>([])
  const [loadingJobs, setLoadingJobs] = useState(true)
  const [deletingJob, setDeletingJob] = useState<string | null>(null)

  const fetchScheduledJobs = async () => {
    try {
      const response = await fetch('/api/schedule')
      if (response.ok) {
        const data = await response.json()
        setScheduledJobs(data.scheduled_jobs)
      }
    } catch {
      // Ignore errors
    } finally {
      setLoadingJobs(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchScheduledJobs()

      // Set default date/time to 1 hour from now
      const now = new Date()
      now.setHours(now.getHours() + 1)
      now.setMinutes(0)
      setScheduledDate(now.toISOString().split('T')[0])
      setScheduledTime(now.toTimeString().slice(0, 5))
    }
  }, [isOpen])

  const handleSubmit = async () => {
    if (!url.trim()) {
      setError('Please enter a URL')
      return
    }
    if (!scheduledDate || !scheduledTime) {
      setError('Please select date and time')
      return
    }

    // Combine date and time into ISO format
    const scheduledAt = new Date(`${scheduledDate}T${scheduledTime}:00`).toISOString()

    // Check if scheduled time is in the future
    if (new Date(scheduledAt) <= new Date()) {
      setError('Scheduled time must be in the future')
      return
    }

    setSubmitting(true)
    setError(null)
    setSuccess(false)

    try {
      const response = await fetch('/api/schedule/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          scheduled_at: scheduledAt,
          priority,
          format,
          quality: 'high',
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to schedule download')
      }

      setSuccess(true)
      setUrl('')
      await fetchScheduledJobs()
      onScheduled?.()

      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule download')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (jobId: string) => {
    if (!confirm('Cancel this scheduled download?')) return

    setDeletingJob(jobId)
    try {
      const response = await fetch(`/api/schedule/${jobId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('Failed to cancel')
      await fetchScheduledJobs()
    } catch {
      setError('Failed to cancel scheduled download')
    } finally {
      setDeletingJob(null)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Calendar className="h-5 w-5 text-primary" />
            Schedule Download
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="p-4 space-y-4">
          {/* URL Input */}
          <div>
            <label className="block text-sm font-medium mb-1">URL</label>
            <Input
              placeholder="https://youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={submitting}
            />
          </div>

          {/* Date/Time */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Date</label>
              <Input
                type="date"
                value={scheduledDate}
                onChange={(e) => setScheduledDate(e.target.value)}
                disabled={submitting}
                min={new Date().toISOString().split('T')[0]}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Time</label>
              <Input
                type="time"
                value={scheduledTime}
                onChange={(e) => setScheduledTime(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>

          {/* Options */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                disabled={submitting}
                className="w-full h-10 px-3 border rounded-md bg-background"
              >
                <option value={1}>Low</option>
                <option value={5}>Normal</option>
                <option value={10}>High</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                disabled={submitting}
                className="w-full h-10 px-3 border rounded-md bg-background"
              >
                <option value="m4a">M4A</option>
                <option value="mp3">MP3</option>
                <option value="mp4">MP4</option>
              </select>
            </div>
          </div>

          {/* Error/Success Messages */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-destructive/10 text-destructive rounded-lg text-sm">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 p-3 bg-green-500/10 text-green-700 dark:text-green-400 rounded-lg text-sm">
              <Check className="h-4 w-4" />
              Download scheduled successfully
            </div>
          )}

          {/* Submit Button */}
          <Button onClick={handleSubmit} disabled={submitting} className="w-full">
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Scheduling...
              </>
            ) : (
              <>
                <Clock className="mr-2 h-4 w-4" />
                Schedule Download
              </>
            )}
          </Button>

          {/* Scheduled Jobs List */}
          <div className="border-t pt-4 mt-4">
            <h3 className="text-sm font-medium mb-3">Scheduled Downloads</h3>
            {loadingJobs ? (
              <div className="flex justify-center py-4">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : scheduledJobs.length === 0 ? (
              <div className="text-center py-4 text-muted-foreground text-sm">
                No scheduled downloads
              </div>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {scheduledJobs.map((job) => (
                  <div
                    key={job.job_id}
                    className="flex items-center gap-2 p-2 bg-muted rounded-lg"
                  >
                    <Clock className="h-4 w-4 text-primary flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="font-mono text-xs truncate">{job.url}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(job.scheduled_at).toLocaleString()}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(job.job_id)}
                      disabled={deletingJob === job.job_id}
                      className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                    >
                      {deletingJob === job.job_id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
