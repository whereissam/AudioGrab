import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Webhook, Loader2, Check, AlertCircle, Send } from 'lucide-react'

interface WebhookConfig {
  default_url: string | null
  retry_attempts: number
  retry_delay: number
}

export function WebhookSettings() {
  const [config, setConfig] = useState<WebhookConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [testUrl, setTestUrl] = useState('')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; error?: string } | null>(null)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/webhooks/config')
      if (response.ok) {
        const data = await response.json()
        setConfig(data)
        if (data.default_url) {
          setTestUrl(data.default_url)
        }
      }
    } catch {
      // Ignore errors
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async () => {
    if (!testUrl.trim()) return

    setTesting(true)
    setTestResult(null)

    try {
      const response = await fetch('/api/webhooks/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: testUrl }),
      })

      const data = await response.json()
      setTestResult(data)
    } catch {
      setTestResult({ success: false, error: 'Request failed' })
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Webhook className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Webhook Settings</h2>
      </div>

      <p className="text-sm text-muted-foreground">
        Configure webhooks to receive notifications when downloads complete or fail.
      </p>

      {/* Configuration Display */}
      {config && (
        <div className="bg-muted rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Default Webhook URL</span>
            <span className="font-mono">{config.default_url || 'Not configured'}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Retry Attempts</span>
            <span>{config.retry_attempts}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Retry Delay</span>
            <span>{config.retry_delay}s</span>
          </div>
        </div>
      )}

      {/* Test Webhook */}
      <div className="border rounded-lg p-4 space-y-4">
        <h3 className="font-medium">Test Webhook</h3>
        <p className="text-sm text-muted-foreground">
          Send a test payload to verify your webhook endpoint is working correctly.
        </p>

        <div className="flex gap-2">
          <Input
            placeholder="https://your-webhook-url.com/hook"
            value={testUrl}
            onChange={(e) => setTestUrl(e.target.value)}
            disabled={testing}
            className="flex-1"
          />
          <Button onClick={handleTest} disabled={testing || !testUrl.trim()}>
            {testing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Send className="h-4 w-4 mr-1" />
                Test
              </>
            )}
          </Button>
        </div>

        {testResult && (
          <div
            className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
              testResult.success
                ? 'bg-green-500/10 text-green-700 dark:text-green-400'
                : 'bg-destructive/10 text-destructive'
            }`}
          >
            {testResult.success ? (
              <>
                <Check className="h-4 w-4" />
                Webhook test successful
              </>
            ) : (
              <>
                <AlertCircle className="h-4 w-4" />
                {testResult.error || 'Webhook test failed'}
              </>
            )}
          </div>
        )}
      </div>

      {/* Webhook Events Documentation */}
      <div className="border rounded-lg p-4 space-y-4">
        <h3 className="font-medium">Webhook Events</h3>
        <div className="space-y-3 text-sm">
          <div className="p-3 bg-muted rounded-lg">
            <div className="font-medium text-primary mb-1">job_completed</div>
            <div className="text-muted-foreground">
              Fired when a download job completes successfully.
            </div>
          </div>
          <div className="p-3 bg-muted rounded-lg">
            <div className="font-medium text-primary mb-1">job_failed</div>
            <div className="text-muted-foreground">
              Fired when a download job fails.
            </div>
          </div>
          <div className="p-3 bg-muted rounded-lg">
            <div className="font-medium text-primary mb-1">batch_completed</div>
            <div className="text-muted-foreground">
              Fired when all jobs in a batch have finished.
            </div>
          </div>
        </div>
      </div>

      {/* Example Payload */}
      <div className="border rounded-lg p-4 space-y-4">
        <h3 className="font-medium">Example Payload</h3>
        <pre className="bg-muted rounded-lg p-4 overflow-x-auto text-xs font-mono">
{`{
  "event": "job_completed",
  "job_id": "abc123",
  "status": "completed",
  "job_type": "download",
  "content_info": {
    "title": "Example Content",
    "duration_seconds": 3600
  },
  "file_path": "/output/example.m4a",
  "file_size_mb": 42.5,
  "error": null,
  "timestamp": "2026-01-30T10:00:00Z"
}`}
        </pre>
      </div>

      <p className="text-xs text-muted-foreground">
        Note: Webhook configuration is managed via environment variables.
        Set <code className="bg-muted px-1 rounded">DEFAULT_WEBHOOK_URL</code> in your .env file.
      </p>
    </div>
  )
}
