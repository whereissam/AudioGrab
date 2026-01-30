import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Reply, Trash2, Clock, User, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { formatDuration } from '@/components/downloader/types'
import type { Annotation } from './AnnotationPanel'

interface AnnotationThreadProps {
  annotation: Annotation
  currentUserId: string
  onReply: (annotationId: string) => void
  onDelete: (annotationId: string) => void
  onSegmentClick?: (start: number, end: number) => void
  replyingTo: string | null
  onSubmitReply: (content: string) => void
  onCancelReply: () => void
}

export function AnnotationThread({
  annotation,
  currentUserId,
  onReply,
  onDelete,
  onSegmentClick,
  replyingTo,
  onSubmitReply,
  onCancelReply,
}: AnnotationThreadProps) {
  const [replyContent, setReplyContent] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isOwner = annotation.user_id === currentUserId
  const isReplying = replyingTo === annotation.id

  const handleSubmitReply = async () => {
    if (!replyContent.trim()) return
    setSubmitting(true)
    await onSubmitReply(replyContent)
    setReplyContent('')
    setSubmitting(false)
  }

  const formatTime = (date: string) => {
    return new Date(date).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="bg-muted/50 rounded-lg p-3 space-y-2">
      {/* Main Annotation */}
      <div className="space-y-2">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium">
              {annotation.user_name || `User ${annotation.user_id.slice(0, 6)}`}
            </span>
            <span className="text-muted-foreground text-xs">
              {formatTime(annotation.created_at)}
            </span>
          </div>
          {isOwner && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDelete(annotation.id)}
              className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          )}
        </div>

        {/* Segment Badge */}
        {annotation.segment_start !== undefined && annotation.segment_end !== undefined && (
          <button
            onClick={() => onSegmentClick?.(annotation.segment_start!, annotation.segment_end!)}
            className="inline-flex items-center gap-1 text-xs bg-primary/10 text-primary px-2 py-0.5 rounded hover:bg-primary/20 transition-colors"
          >
            <Clock className="h-3 w-3" />
            {formatDuration(annotation.segment_start)} - {formatDuration(annotation.segment_end)}
          </button>
        )}

        {/* Content */}
        <p className="text-sm">{annotation.content}</p>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onReply(annotation.id)}
            className="h-7 px-2 text-xs"
          >
            <Reply className="h-3 w-3 mr-1" />
            Reply
          </Button>
        </div>

        {/* Reply Form */}
        {isReplying && (
          <div className="mt-2 flex gap-2">
            <Input
              placeholder="Write a reply..."
              value={replyContent}
              onChange={(e) => setReplyContent(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmitReply()
                }
                if (e.key === 'Escape') {
                  onCancelReply()
                }
              }}
              disabled={submitting}
              className="flex-1 h-8 text-sm"
            />
            <Button
              size="sm"
              onClick={handleSubmitReply}
              disabled={!replyContent.trim() || submitting}
              className="h-8"
            >
              {submitting ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Reply'}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onCancelReply}
              disabled={submitting}
              className="h-8"
            >
              Cancel
            </Button>
          </div>
        )}
      </div>

      {/* Replies */}
      {annotation.replies.length > 0 && (
        <div className="ml-4 border-l-2 border-muted pl-3 space-y-2">
          {annotation.replies.map((reply) => (
            <div key={reply.id} className="space-y-1">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-medium">
                    {reply.user_name || `User ${reply.user_id.slice(0, 6)}`}
                  </span>
                  <span className="text-muted-foreground">{formatTime(reply.created_at)}</span>
                </div>
                {reply.user_id === currentUserId && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDelete(reply.id)}
                    className="h-5 w-5 p-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </div>
              <p className="text-sm text-muted-foreground">{reply.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
