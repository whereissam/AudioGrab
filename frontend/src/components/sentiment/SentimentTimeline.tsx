import { useMemo } from 'react'

interface TimeWindow {
  window_index: number
  start: number
  end: number
  avg_polarity: number
  avg_heat_score: number
  dominant_emotion: string
  segment_count: number
}

interface SentimentTimelineProps {
  windows: TimeWindow[]
  onWindowClick?: (window: TimeWindow) => void
  totalDuration?: number
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function getHeatColor(heatScore: number): string {
  if (heatScore >= 0.8) return 'bg-red-500'
  if (heatScore >= 0.6) return 'bg-orange-500'
  if (heatScore >= 0.4) return 'bg-yellow-500'
  if (heatScore >= 0.2) return 'bg-green-500'
  return 'bg-blue-500'
}

export function SentimentTimeline({ windows, onWindowClick, totalDuration }: SentimentTimelineProps) {
  const duration = useMemo(() => {
    if (totalDuration) return totalDuration
    if (windows.length === 0) return 0
    return windows[windows.length - 1].end
  }, [windows, totalDuration])

  if (windows.length === 0) {
    return (
      <div className="text-center text-muted-foreground text-sm py-4">
        No timeline data available
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Main heatmap bar */}
      <div className="relative">
        <div className="flex h-10 rounded-lg overflow-hidden bg-muted">
          {windows.map((window) => {
            const widthPercent = ((window.end - window.start) / duration) * 100
            return (
              <button
                key={window.window_index}
                className={`${getHeatColor(window.avg_heat_score)} hover:opacity-80 transition-opacity relative group`}
                style={{ width: `${widthPercent}%` }}
                onClick={() => onWindowClick?.(window)}
                title={`${formatTime(window.start)} - ${formatTime(window.end)}\nHeat: ${(window.avg_heat_score * 100).toFixed(0)}%\nEmotion: ${window.dominant_emotion}`}
              >
                {/* Tooltip */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-popover text-popover-foreground text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                  <div className="font-medium">{formatTime(window.start)} - {formatTime(window.end)}</div>
                  <div>Heat: {(window.avg_heat_score * 100).toFixed(0)}%</div>
                  <div className="capitalize">{window.dominant_emotion}</div>
                </div>
              </button>
            )
          })}
        </div>

        {/* Time markers */}
        <div className="flex justify-between text-xs text-muted-foreground mt-1">
          <span>{formatTime(0)}</span>
          {duration > 120 && <span>{formatTime(duration / 2)}</span>}
          <span>{formatTime(duration)}</span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="font-medium">Intensity:</span>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-blue-500" />
          <span>Calm</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-green-500" />
          <span>Low</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-yellow-500" />
          <span>Moderate</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-orange-500" />
          <span>Warm</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-red-500" />
          <span>Intense</span>
        </div>
      </div>
    </div>
  )
}

// Mini version for compact display
export function SentimentTimelineMini({ windows }: { windows: TimeWindow[] }) {
  const duration = useMemo(() => {
    if (windows.length === 0) return 0
    return windows[windows.length - 1].end
  }, [windows])

  if (windows.length === 0) return null

  return (
    <div className="flex h-2 rounded overflow-hidden bg-muted">
      {windows.map((window) => {
        const widthPercent = ((window.end - window.start) / duration) * 100
        return (
          <div
            key={window.window_index}
            className={getHeatColor(window.avg_heat_score)}
            style={{ width: `${widthPercent}%` }}
          />
        )
      })}
    </div>
  )
}
