import { MessageSquare } from 'lucide-react'
import type { Annotation } from './AnnotationPanel'

interface AnnotationMarkerProps {
  annotations: Annotation[]
  totalDuration: number
  onClick: (annotation: Annotation) => void
}

export function AnnotationMarker({ annotations, totalDuration, onClick }: AnnotationMarkerProps) {
  // Filter annotations that have segment times
  const segmentAnnotations = annotations.filter(
    (a) => a.segment_start !== undefined && a.segment_end !== undefined
  )

  if (segmentAnnotations.length === 0) return null

  return (
    <div className="relative h-6 bg-muted rounded-lg overflow-hidden">
      {segmentAnnotations.map((annotation) => {
        const left = ((annotation.segment_start ?? 0) / totalDuration) * 100
        const width = Math.max(
          (((annotation.segment_end ?? 0) - (annotation.segment_start ?? 0)) / totalDuration) * 100,
          1 // Minimum 1% width for visibility
        )

        return (
          <button
            key={annotation.id}
            onClick={() => onClick(annotation)}
            className="absolute top-0 h-full bg-primary/30 hover:bg-primary/50 transition-colors group"
            style={{
              left: `${left}%`,
              width: `${width}%`,
            }}
            title={`${annotation.user_name || 'Anonymous'}: ${annotation.content.slice(0, 50)}${
              annotation.content.length > 50 ? '...' : ''
            }`}
          >
            <MessageSquare className="h-3 w-3 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        )
      })}
    </div>
  )
}
