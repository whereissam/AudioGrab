import { useState } from 'react'
import { ArrowLeft, Loader2, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  SubscriptionType,
  SUBSCRIPTION_TYPES,
  WHISPER_MODELS,
  OUTPUT_FORMATS,
} from './types'

interface AddSubscriptionFormProps {
  onSuccess: () => void
  onCancel: () => void
}

export function AddSubscriptionForm({ onSuccess, onCancel }: AddSubscriptionFormProps) {
  const [name, setName] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [subscriptionType, setSubscriptionType] = useState<SubscriptionType>('rss')
  const [autoTranscribe, setAutoTranscribe] = useState(false)
  const [transcribeModel, setTranscribeModel] = useState('base')
  const [downloadLimit, setDownloadLimit] = useState(10)
  const [outputFormat, setOutputFormat] = useState('m4a')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sourceUrl.trim()) {
      setError('Please enter a source URL')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/subscriptions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim() || undefined,
          source_url: sourceUrl.trim(),
          subscription_type: subscriptionType,
          auto_transcribe: autoTranscribe,
          transcribe_model: transcribeModel,
          download_limit: downloadLimit,
          output_format: outputFormat,
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to create subscription')
      }

      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create subscription')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-card rounded-xl shadow-lg p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Button variant="ghost" size="icon" onClick={onCancel}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h2 className="text-xl font-semibold text-foreground">Add Subscription</h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Subscription Type */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Subscription Type
          </label>
          <div className="grid gap-2">
            {SUBSCRIPTION_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => setSubscriptionType(type.value)}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  subscriptionType === type.value
                    ? 'border-primary bg-primary/10'
                    : 'border-border bg-background hover:border-primary/50'
                }`}
              >
                <div className="font-medium text-foreground">{type.label}</div>
                <div className="text-xs text-muted-foreground">{type.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Source URL */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Source URL
          </label>
          <Input
            type="url"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder={
              subscriptionType === 'rss'
                ? 'https://podcasts.apple.com/us/podcast/show/id123456789'
                : subscriptionType === 'youtube_channel'
                ? 'https://www.youtube.com/@channel'
                : 'https://www.youtube.com/playlist?list=PLxxx'
            }
            className="h-12"
            disabled={loading}
          />
          <p className="text-xs text-muted-foreground mt-1">
            {subscriptionType === 'rss' && 'Apple Podcasts URL or direct RSS feed URL'}
            {subscriptionType === 'youtube_channel' && 'YouTube channel URL (/@handle or /channel/id)'}
            {subscriptionType === 'youtube_playlist' && 'YouTube playlist URL'}
          </p>
        </div>

        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Display Name (optional)
          </label>
          <Input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Auto-detected from source"
            className="h-12"
            disabled={loading}
          />
        </div>

        {/* Download Limit */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Keep Last {downloadLimit} Downloads
          </label>
          <input
            type="range"
            min={1}
            max={50}
            value={downloadLimit}
            onChange={(e) => setDownloadLimit(Number(e.target.value))}
            className="w-full"
            disabled={loading}
          />
          <p className="text-xs text-muted-foreground">
            Older downloads will be automatically deleted
          </p>
        </div>

        {/* Output Format */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Output Format
          </label>
          <div className="flex gap-2">
            {OUTPUT_FORMATS.map((fmt) => (
              <button
                key={fmt.value}
                type="button"
                onClick={() => setOutputFormat(fmt.value)}
                className={`flex-1 p-2 rounded-lg border-2 transition-all ${
                  outputFormat === fmt.value
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-background text-foreground hover:border-primary/50'
                }`}
                disabled={loading}
              >
                {fmt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Auto Transcribe */}
        <div className="border rounded-lg p-4">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={autoTranscribe}
              onChange={(e) => setAutoTranscribe(e.target.checked)}
              className="w-5 h-5 rounded"
              disabled={loading}
            />
            <div>
              <div className="font-medium text-foreground">Auto-transcribe</div>
              <div className="text-xs text-muted-foreground">
                Automatically transcribe downloaded content
              </div>
            </div>
          </label>

          {autoTranscribe && (
            <div className="mt-4">
              <label className="block text-sm font-medium text-foreground mb-2">
                Whisper Model
              </label>
              <div className="flex flex-wrap gap-2">
                {WHISPER_MODELS.map((model) => (
                  <button
                    key={model.value}
                    type="button"
                    onClick={() => setTranscribeModel(model.value)}
                    className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                      transcribeModel === model.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border bg-background text-foreground hover:border-primary/50'
                    }`}
                    disabled={loading}
                  >
                    {model.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-destructive/10 text-destructive p-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={loading}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button type="submit" disabled={loading} className="flex-1">
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="h-4 w-4 mr-2" />
                Add Subscription
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
