import { createFileRoute } from '@tanstack/react-router'
import { SubscriptionList } from '@/components/subscriptions'

export const Route = createFileRoute('/subscriptions')({
  component: SubscriptionsPage,
})

function SubscriptionsPage() {
  return (
    <div className="flex-1 py-6">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Subscriptions</h1>
          <p className="text-sm text-muted-foreground">
            Auto-download new content from RSS feeds and YouTube
          </p>
        </div>

        {/* Content */}
        <SubscriptionList />
      </div>
    </div>
  )
}
