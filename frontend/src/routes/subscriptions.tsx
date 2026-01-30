import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SubscriptionList } from '@/components/subscriptions'

export const Route = createFileRoute('/subscriptions')({
  component: SubscriptionsPage,
})

function SubscriptionsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted">
      <div className="max-w-6xl mx-auto p-4 sm:p-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Subscriptions</h1>
            <p className="text-sm text-muted-foreground">
              Auto-download new content from RSS feeds and YouTube
            </p>
          </div>
        </div>

        {/* Content */}
        <SubscriptionList />
      </div>
    </div>
  )
}
