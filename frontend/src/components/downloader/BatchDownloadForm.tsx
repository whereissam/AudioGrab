import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Loader2, Upload, X, Download, AlertCircle, Check, Clock } from 'lucide-react'

interface BatchJob {
  job_id: string
  status: string
  url: string
  progress?: number
  error?: string
}

interface BatchStatus {
  batch_id: string
  name: string | null
  total_jobs: number
  completed_jobs: number
  failed_jobs: number
  status: string
}

type BatchDownloadStatus = 'idle' | 'creating' | 'processing' | 'completed' | 'error'

export function BatchDownloadForm() {
  const [urlInput, setUrlInput] = useState('')
  const [urls, setUrls] = useState<string[]>([])
  const [batchName, setBatchName] = useState('')
  const [priority, setPriority] = useState(5)
  const [format, setFormat] = useState('m4a')
  const [status, setStatus] = useState<BatchDownloadStatus>('idle')
  const [message, setMessage] = useState('')
  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null)
  const [jobs, setJobs] = useState<BatchJob[]>([])

  const handleAddUrl = () => {
    const trimmed = urlInput.trim()
    if (trimmed && !urls.includes(trimmed)) {
      setUrls([...urls, trimmed])
      setUrlInput('')
    }
  }

  const handleRemoveUrl = (urlToRemove: string) => {
    setUrls(urls.filter(u => u !== urlToRemove))
  }

  const handlePasteUrls = (text: string) => {
    const lines = text.split('\n')
      .map(l => l.trim())
      .filter(l => l && !l.startsWith('#') && !urls.includes(l))
    if (lines.length > 0) {
      setUrls([...urls, ...lines])
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const text = await file.text()
    handlePasteUrls(text)
    e.target.value = ''
  }

  const handleSubmit = async () => {
    if (urls.length === 0) {
      setStatus('error')
      setMessage('Please add at least one URL')
      return
    }

    setStatus('creating')
    setMessage('Creating batch...')
    setBatchStatus(null)
    setJobs([])

    try {
      const response = await fetch('/api/batch/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          urls,
          name: batchName || undefined,
          priority,
          format,
          quality: 'high',
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to create batch')
      }

      const data = await response.json()
      setBatchStatus(data)
      setStatus('processing')
      setMessage(`Batch created with ${data.total_jobs} jobs`)

      // Start polling for batch status
      pollBatchStatus(data.batch_id)
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Failed to create batch')
    }
  }

  const pollBatchStatus = async (batchId: string) => {
    try {
      // Poll batch status
      const statusRes = await fetch(`/api/batch/${batchId}`)
      const statusData = await statusRes.json()
      setBatchStatus(statusData)

      // Fetch jobs
      const jobsRes = await fetch(`/api/batch/${batchId}/jobs`)
      const jobsData = await jobsRes.json()
      setJobs(jobsData.jobs.map((j: { job_id: string; status: string; source_url: string; progress?: number; error?: string }) => ({
        job_id: j.job_id,
        status: j.status,
        url: j.source_url,
        progress: j.progress,
        error: j.error,
      })))

      // Continue polling if not complete
      if (statusData.status !== 'completed' && statusData.status !== 'completed_with_errors') {
        setTimeout(() => pollBatchStatus(batchId), 2000)
      } else {
        setStatus('completed')
        setMessage(
          statusData.failed_jobs > 0
            ? `Completed with ${statusData.failed_jobs} failed jobs`
            : 'All downloads completed'
        )
      }
    } catch {
      setStatus('error')
      setMessage('Failed to fetch batch status')
    }
  }

  const handleReset = () => {
    setUrls([])
    setBatchName('')
    setPriority(5)
    setStatus('idle')
    setMessage('')
    setBatchStatus(null)
    setJobs([])
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold">Batch Download</h2>
        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
          {urls.length} URL{urls.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* URL Input */}
      <div className="space-y-2">
        <div className="flex gap-2">
          <Input
            placeholder="Enter URL and press Enter"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleAddUrl()
              }
            }}
            onPaste={(e) => {
              const text = e.clipboardData.getData('text')
              if (text.includes('\n')) {
                e.preventDefault()
                handlePasteUrls(text)
              }
            }}
            disabled={status === 'creating' || status === 'processing'}
            className="flex-1"
          />
          <Button
            variant="outline"
            onClick={handleAddUrl}
            disabled={!urlInput.trim() || status === 'creating' || status === 'processing'}
          >
            Add
          </Button>
        </div>

        <div className="flex gap-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="file"
              accept=".txt"
              onChange={handleFileUpload}
              className="hidden"
              disabled={status === 'creating' || status === 'processing'}
            />
            <Button variant="outline" size="sm" asChild>
              <span>
                <Upload className="h-4 w-4 mr-1" />
                Upload file
              </span>
            </Button>
          </label>
          <span className="text-xs text-muted-foreground self-center">
            Text file with one URL per line
          </span>
        </div>
      </div>

      {/* URL List */}
      {urls.length > 0 && (
        <div className="border rounded-lg max-h-40 overflow-y-auto">
          {urls.map((url, i) => (
            <div key={i} className="flex items-center gap-2 p-2 border-b last:border-b-0 text-sm">
              <span className="flex-1 truncate font-mono text-xs">{url}</span>
              <button
                onClick={() => handleRemoveUrl(url)}
                disabled={status === 'creating' || status === 'processing'}
                className="text-muted-foreground hover:text-destructive"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Options */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Batch Name (optional)</label>
          <Input
            placeholder="My batch"
            value={batchName}
            onChange={(e) => setBatchName(e.target.value)}
            disabled={status === 'creating' || status === 'processing'}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Priority</label>
          <select
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            disabled={status === 'creating' || status === 'processing'}
            className="w-full h-10 px-3 border rounded-md bg-background"
          >
            <option value={1}>Low (1)</option>
            <option value={5}>Normal (5)</option>
            <option value={10}>High (10)</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Format</label>
        <div className="flex gap-2">
          {['m4a', 'mp3', 'mp4'].map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              disabled={status === 'creating' || status === 'processing'}
              className={`px-4 py-2 rounded-lg border-2 transition-all uppercase text-sm font-medium ${
                format === f
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border hover:border-primary/50'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Submit Button */}
      <Button
        onClick={handleSubmit}
        disabled={urls.length === 0 || status === 'creating' || status === 'processing'}
        className="w-full"
      >
        {status === 'creating' || status === 'processing' ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            {status === 'creating' ? 'Creating batch...' : 'Processing...'}
          </>
        ) : (
          <>
            <Download className="mr-2 h-4 w-4" />
            Start Batch Download ({urls.length} URLs)
          </>
        )}
      </Button>

      {/* Status Message */}
      {message && status !== 'idle' && (
        <div
          className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
            status === 'error'
              ? 'bg-destructive/10 text-destructive'
              : status === 'completed'
              ? 'bg-green-500/10 text-green-700 dark:text-green-400'
              : 'bg-primary/10 text-primary'
          }`}
        >
          {status === 'error' && <AlertCircle className="h-4 w-4" />}
          {status === 'completed' && <Check className="h-4 w-4" />}
          {(status === 'creating' || status === 'processing') && <Loader2 className="h-4 w-4 animate-spin" />}
          <span>{message}</span>
        </div>
      )}

      {/* Batch Progress */}
      {batchStatus && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-medium">{batchStatus.name || 'Batch'}</span>
            <span className="text-sm text-muted-foreground">
              {batchStatus.completed_jobs + batchStatus.failed_jobs} / {batchStatus.total_jobs}
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all"
              style={{
                width: `${((batchStatus.completed_jobs + batchStatus.failed_jobs) / batchStatus.total_jobs) * 100}%`,
              }}
            />
          </div>

          {/* Job list */}
          <div className="max-h-48 overflow-y-auto space-y-1">
            {jobs.map((job) => (
              <div key={job.job_id} className="flex items-center gap-2 text-xs p-1.5 rounded bg-muted/50">
                {job.status === 'completed' && <Check className="h-3 w-3 text-green-500" />}
                {job.status === 'failed' && <AlertCircle className="h-3 w-3 text-destructive" />}
                {job.status === 'pending' && <Clock className="h-3 w-3 text-muted-foreground" />}
                {(job.status === 'downloading' || job.status === 'converting') && (
                  <Loader2 className="h-3 w-3 animate-spin text-primary" />
                )}
                <span className="truncate flex-1 font-mono">{job.url}</span>
                {job.error && <span className="text-destructive truncate max-w-[100px]">{job.error}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reset button */}
      {status === 'completed' && (
        <Button variant="outline" onClick={handleReset} className="w-full">
          New Batch
        </Button>
      )}
    </div>
  )
}
