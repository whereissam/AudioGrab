import { useState, useEffect } from 'react'
import {
  ArrowLeft,
  Loader2,
  RefreshCw,
  RotateCcw,
  Trash2,
  Download,
  FileText,
  ExternalLink,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Subscription,
  SubscriptionItem,
  SubscriptionItemListResponse,
  formatRelativeTime,
  getStatusColor,
} from './types'

interface SubscriptionDetailProps {
  subscription: Subscription
  onBack: () => void
  onRefresh: () => void
}

export function SubscriptionDetail({
  subscription,
  onBack,
  onRefresh,
}: SubscriptionDetailProps) {
  const [items, setItems] = useState<SubscriptionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [retryingIds, setRetryingIds] = useState<Set<string>>(new Set())

  const fetchItems = async () => {
    try {
      const response = await fetch(
        `/api/subscriptions/${subscription.id}/items?limit=100`
      )
      if (!response.ok) throw new Error('Failed to fetch items')
      const data: SubscriptionItemListResponse = await response.json()
      setItems(data.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load items')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchItems()
  }, [subscription.id])

  const handleCheck = async () => {
    setChecking(true)
    try {
      const response = await fetch(
        `/api/subscriptions/${subscription.id}/check`,
        { method: 'POST' }
      )
      if (!response.ok) throw new Error('Failed to check subscription')
      await fetchItems()
      onRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check')
    } finally {
      setChecking(false)
    }
  }

  const handleRetry = async (itemId: string) => {
    setRetryingIds((prev) => new Set(prev).add(itemId))
    try {
      const response = await fetch(
        `/api/subscriptions/${subscription.id}/items/${itemId}/retry`,
        { method: 'POST' }
      )
      if (!response.ok) throw new Error('Failed to retry item')
      await fetchItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry')
    } finally {
      setRetryingIds((prev) => {
        const next = new Set(prev)
        next.delete(itemId)
        return next
      })
    }
  }

  const handleDeleteItem = async (itemId: string) => {
    if (!confirm('Delete this item and its files?')) return
    try {
      const response = await fetch(
        `/api/subscriptions/${subscription.id}/items/${itemId}`,
        { method: 'DELETE' }
      )
      if (!response.ok) throw new Error('Failed to delete item')
      await fetchItems()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="bg-card rounded-xl shadow-lg p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <Button variant="ghost" size="icon" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-foreground">
              {subscription.name}
            </h2>
            <p className="text-sm text-muted-foreground truncate">
              {subscription.source_url}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={handleCheck}
            disabled={checking || !subscription.enabled}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${checking ? 'animate-spin' : ''}`}
            />
            Check Now
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 text-center">
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-foreground">
              {subscription.total_downloaded}
            </div>
            <div className="text-xs text-muted-foreground">Total Downloaded</div>
          </div>
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {items.filter((i) => i.status === 'pending').length}
            </div>
            <div className="text-xs text-muted-foreground">Pending</div>
          </div>
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {items.filter((i) => i.status === 'completed').length}
            </div>
            <div className="text-xs text-muted-foreground">Completed</div>
          </div>
          <div className="bg-muted/50 rounded-lg p-3">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {items.filter((i) => i.status === 'failed').length}
            </div>
            <div className="text-xs text-muted-foreground">Failed</div>
          </div>
        </div>

        {/* Settings summary */}
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <span className="px-2 py-1 bg-muted rounded">
            Format: {subscription.output_format.toUpperCase()}
          </span>
          <span className="px-2 py-1 bg-muted rounded">
            Limit: {subscription.download_limit}
          </span>
          {subscription.auto_transcribe && (
            <span className="px-2 py-1 bg-primary/10 text-primary rounded">
              Auto-transcribe ({subscription.transcribe_model})
            </span>
          )}
          <span
            className={`px-2 py-1 rounded ${
              subscription.enabled
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
            }`}
          >
            {subscription.enabled ? 'Enabled' : 'Paused'}
          </span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg mb-4">
          {error}
        </div>
      )}

      {/* Items list */}
      <div className="bg-card rounded-xl shadow-lg overflow-hidden">
        <div className="p-4 border-b">
          <h3 className="font-semibold text-foreground">
            Items ({items.length})
          </h3>
        </div>

        {loading ? (
          <div className="flex items-center justify-center p-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center p-12 text-muted-foreground">
            No items yet. Click "Check Now" to fetch content.
          </div>
        ) : (
          <div className="divide-y">
            {items.map((item) => (
              <div
                key={item.id}
                className="p-4 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(
                          item.status
                        )}`}
                      >
                        {item.status}
                      </span>
                      {item.published_at && (
                        <span className="text-xs text-muted-foreground">
                          {formatRelativeTime(item.published_at)}
                        </span>
                      )}
                    </div>
                    <h4 className="font-medium text-foreground truncate">
                      {item.title || item.content_id}
                    </h4>
                    {item.error && (
                      <p className="text-xs text-destructive mt-1 truncate">
                        {item.error}
                      </p>
                    )}
                    {item.file_path && (
                      <p className="text-xs text-muted-foreground mt-1 truncate">
                        {item.file_path}
                      </p>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {item.content_url && (
                      <Button
                        variant="ghost"
                        size="icon"
                        asChild
                        className="h-8 w-8"
                      >
                        <a
                          href={item.content_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </Button>
                    )}
                    {item.file_path && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        title="Download"
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    )}
                    {item.transcription_path && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        title="Transcription"
                      >
                        <FileText className="h-4 w-4" />
                      </Button>
                    )}
                    {(item.status === 'failed' || item.status === 'skipped') && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleRetry(item.id)}
                        disabled={retryingIds.has(item.id)}
                      >
                        <RotateCcw
                          className={`h-4 w-4 ${
                            retryingIds.has(item.id) ? 'animate-spin' : ''
                          }`}
                        />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => handleDeleteItem(item.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
