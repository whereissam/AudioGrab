import { Play, Pause, Trash2, RefreshCw, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Subscription,
  formatRelativeTime,
  getPlatformIcon,
} from './types'

interface SubscriptionCardProps {
  subscription: Subscription
  onToggle: (id: string, enabled: boolean) => void
  onCheck: (id: string) => void
  onDelete: (id: string) => void
  onClick: (id: string) => void
  isChecking?: boolean
}

export function SubscriptionCard({
  subscription,
  onToggle,
  onCheck,
  onDelete,
  onClick,
  isChecking,
}: SubscriptionCardProps) {
  const typeIcon = getPlatformIcon(subscription.subscription_type)

  return (
    <div
      className={`bg-card rounded-xl shadow-md border p-4 transition-all hover:shadow-lg ${
        !subscription.enabled ? 'opacity-60' : ''
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div
          className="flex-1 cursor-pointer"
          onClick={() => onClick(subscription.id)}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">{typeIcon}</span>
            <h3 className="font-semibold text-foreground truncate">
              {subscription.name}
            </h3>
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {subscription.source_url}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onClick(subscription.id)}
          className="flex-shrink-0"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 mb-4 text-center">
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="text-lg font-bold text-foreground">
            {subscription.total_downloaded}
          </div>
          <div className="text-xs text-muted-foreground">Downloaded</div>
        </div>
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="text-lg font-bold text-yellow-600 dark:text-yellow-400">
            {subscription.pending_count ?? 0}
          </div>
          <div className="text-xs text-muted-foreground">Pending</div>
        </div>
        <div className="bg-muted/50 rounded-lg p-2">
          <div className="text-lg font-bold text-green-600 dark:text-green-400">
            {subscription.completed_count ?? 0}
          </div>
          <div className="text-xs text-muted-foreground">Completed</div>
        </div>
      </div>

      {/* Last checked */}
      <div className="text-xs text-muted-foreground mb-4">
        {subscription.last_checked_at ? (
          <>Last checked: {formatRelativeTime(subscription.last_checked_at)}</>
        ) : (
          'Never checked'
        )}
        {subscription.auto_transcribe && (
          <span className="ml-2 px-1.5 py-0.5 bg-primary/10 text-primary rounded text-[10px]">
            Auto-transcribe
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant={subscription.enabled ? 'outline' : 'default'}
          size="sm"
          onClick={() => onToggle(subscription.id, !subscription.enabled)}
          className="flex-1"
        >
          {subscription.enabled ? (
            <>
              <Pause className="h-4 w-4 mr-1" />
              Pause
            </>
          ) : (
            <>
              <Play className="h-4 w-4 mr-1" />
              Enable
            </>
          )}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onCheck(subscription.id)}
          disabled={isChecking || !subscription.enabled}
        >
          <RefreshCw className={`h-4 w-4 ${isChecking ? 'animate-spin' : ''}`} />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onDelete(subscription.id)}
          className="text-destructive hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
