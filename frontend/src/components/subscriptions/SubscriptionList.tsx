import { useState, useEffect } from 'react'
import { Plus, Loader2, Rss } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SubscriptionCard } from './SubscriptionCard'
import { AddSubscriptionForm } from './AddSubscriptionForm'
import { SubscriptionDetail } from './SubscriptionDetail'
import { Subscription, SubscriptionListResponse } from './types'

export function SubscriptionList() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [checkingIds, setCheckingIds] = useState<Set<string>>(new Set())

  const fetchSubscriptions = async () => {
    try {
      const response = await fetch('/api/subscriptions')
      if (!response.ok) throw new Error('Failed to fetch subscriptions')
      const data: SubscriptionListResponse = await response.json()
      setSubscriptions(data.subscriptions)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load subscriptions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSubscriptions()
  }, [])

  const handleToggle = async (id: string, enabled: boolean) => {
    try {
      const response = await fetch(`/api/subscriptions/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      })
      if (!response.ok) throw new Error('Failed to update subscription')
      await fetchSubscriptions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update subscription')
    }
  }

  const handleCheck = async (id: string) => {
    setCheckingIds((prev) => new Set(prev).add(id))
    try {
      const response = await fetch(`/api/subscriptions/${id}/check`, {
        method: 'POST',
      })
      if (!response.ok) throw new Error('Failed to check subscription')
      await fetchSubscriptions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check subscription')
    } finally {
      setCheckingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this subscription?')) return
    try {
      const response = await fetch(`/api/subscriptions/${id}`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error('Failed to delete subscription')
      await fetchSubscriptions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete subscription')
    }
  }

  const handleAddSuccess = () => {
    setShowAddForm(false)
    fetchSubscriptions()
  }

  // Show detail view if a subscription is selected
  if (selectedId) {
    const subscription = subscriptions.find((s) => s.id === selectedId)
    if (subscription) {
      return (
        <SubscriptionDetail
          subscription={subscription}
          onBack={() => setSelectedId(null)}
          onRefresh={fetchSubscriptions}
        />
      )
    }
  }

  // Show add form
  if (showAddForm) {
    return (
      <div className="max-w-xl mx-auto">
        <AddSubscriptionForm
          onSuccess={handleAddSuccess}
          onCancel={() => setShowAddForm(false)}
        />
      </div>
    )
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Empty state
  if (subscriptions.length === 0) {
    return (
      <div className="text-center p-12">
        <Rss className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
        <h2 className="text-xl font-semibold text-foreground mb-2">
          No Subscriptions Yet
        </h2>
        <p className="text-muted-foreground mb-6">
          Add RSS feeds, YouTube channels, or playlists to automatically download new content.
        </p>
        <Button onClick={() => setShowAddForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Subscription
        </Button>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-foreground">
          Subscriptions ({subscriptions.length})
        </h2>
        <Button onClick={() => setShowAddForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg mb-4">
          {error}
        </div>
      )}

      {/* Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {subscriptions.map((sub) => (
          <SubscriptionCard
            key={sub.id}
            subscription={sub}
            onToggle={handleToggle}
            onCheck={handleCheck}
            onDelete={handleDelete}
            onClick={setSelectedId}
            isChecking={checkingIds.has(sub.id)}
          />
        ))}
      </div>
    </div>
  )
}
