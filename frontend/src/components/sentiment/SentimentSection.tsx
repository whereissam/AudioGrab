import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Flame, Loader2, ChevronDown, Clock, Zap } from 'lucide-react'
import { SentimentTimeline } from './SentimentTimeline'

interface SentimentEmotions {
  joy: number
  anger: number
  fear: number
  surprise: number
  sadness: number
}

interface SentimentSegment {
  segment_index: number
  start: number
  end: number
  text: string
  polarity: number
  energy: string
  energy_score: number
  excitement: number
  emotions: SentimentEmotions
  heat_score: number
  is_heated: boolean
  speaker?: string
}

interface TimeWindow {
  window_index: number
  start: number
  end: number
  avg_polarity: number
  avg_heat_score: number
  dominant_emotion: string
  segment_count: number
}

interface PeakMoment {
  timestamp: number
  description: string
  heat_score: number
}

interface EmotionalArc {
  overall_sentiment: string
  avg_heat_score: number
  peak_moments: PeakMoment[]
  dominant_emotions: string[]
  emotional_journey: string
  total_heated_segments: number
  heated_percentage: number
}

interface SentimentData {
  success: boolean
  job_id: string
  segments: SentimentSegment[]
  time_windows: TimeWindow[]
  emotional_arc?: EmotionalArc
  model?: string
  provider?: string
  tokens_used?: number
  error?: string
}

interface SentimentSectionProps {
  jobId: string
  hasSegments: boolean
  onTimestampClick?: (timestamp: number) => void
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function getEmotionEmoji(emotion: string): string {
  const emojis: Record<string, string> = {
    joy: '😊',
    anger: '😠',
    fear: '😨',
    surprise: '😲',
    sadness: '😢',
  }
  return emojis[emotion] || '😐'
}

function getSentimentBadge(sentiment: string): { color: string; label: string } {
  switch (sentiment) {
    case 'positive':
      return { color: 'bg-green-500/20 text-green-600', label: 'Positive' }
    case 'negative':
      return { color: 'bg-red-500/20 text-red-600', label: 'Negative' }
    case 'mixed':
      return { color: 'bg-purple-500/20 text-purple-600', label: 'Mixed' }
    default:
      return { color: 'bg-gray-500/20 text-gray-600', label: 'Neutral' }
  }
}

export function SentimentSection({ jobId, hasSegments, onTimestampClick }: SentimentSectionProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<SentimentData | null>(null)
  const [showHotMoments, setShowHotMoments] = useState(false)
  const [available, setAvailable] = useState<boolean | null>(null)
  const [unavailableReason, setUnavailableReason] = useState<string | null>(null)

  // Check availability on mount
  useEffect(() => {
    if (!jobId) return

    fetch(`/api/jobs/${jobId}/sentiment/available`)
      .then(res => res.json())
      .then(data => {
        setAvailable(data.available)
        setUnavailableReason(data.reason || null)
      })
      .catch(() => {
        setAvailable(false)
        setUnavailableReason('Failed to check availability')
      })

    // Try to load cached results
    fetch(`/api/jobs/${jobId}/sentiment`)
      .then(res => {
        if (res.ok) return res.json()
        return null
      })
      .then(data => {
        if (data && data.success) {
          setData(data)
        }
      })
      .catch(() => {})
  }, [jobId])

  const handleAnalyze = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/jobs/${jobId}/analyze-sentiment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ window_size: 30 }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Analysis failed')
      }

      const result = await response.json()
      if (result.success) {
        setData(result)
      } else {
        setError(result.error || 'Analysis failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const handleWindowClick = (window: TimeWindow) => {
    onTimestampClick?.(window.start)
  }

  const handleMomentClick = (timestamp: number) => {
    onTimestampClick?.(timestamp)
  }

  // Not available
  if (available !== null && available === false) {
    return (
      <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 text-muted-foreground">
        <div className="flex items-center gap-2 mb-3">
          <Flame className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
          <span className="font-medium text-sm sm:text-base">Sentiment Analysis</span>
        </div>
        <div className="bg-muted rounded-lg p-3 text-xs sm:text-sm">
          {unavailableReason || 'Sentiment analysis is not available for this transcription.'}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card rounded-xl shadow-lg p-3 sm:p-4 text-muted-foreground">
      <div className="flex items-center gap-2 mb-3 sm:mb-4">
        <Flame className="h-4 w-4 sm:h-5 sm:w-5 text-primary" />
        <span className="font-medium text-sm sm:text-base">Sentiment & Vibe Analysis</span>
      </div>

      {/* Analysis button */}
      {!data && (
        <Button
          onClick={handleAnalyze}
          disabled={loading || !hasSegments || !available}
          className="w-full mb-3 sm:mb-4 h-10 sm:h-11"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              <span className="text-sm">Analyzing emotions...</span>
            </>
          ) : (
            <>
              <Flame className="mr-2 h-4 w-4" />
              <span className="text-sm">Analyze Sentiment</span>
            </>
          )}
        </Button>
      )}

      {/* Error */}
      {error && (
        <div className="bg-destructive/10 text-destructive rounded-lg p-2.5 sm:p-3 mb-3 sm:mb-4 text-xs sm:text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {data && data.success && (
        <div className="space-y-4">
          {/* Emotional Arc Summary */}
          {data.emotional_arc && (
            <div className="space-y-3">
              {/* Overall sentiment badge and stats */}
              <div className="flex flex-wrap items-center gap-2">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSentimentBadge(data.emotional_arc.overall_sentiment).color}`}>
                  {getSentimentBadge(data.emotional_arc.overall_sentiment).label}
                </span>
                <span className="text-xs text-muted-foreground">
                  {(data.emotional_arc.avg_heat_score * 100).toFixed(0)}% avg intensity
                </span>
                {data.emotional_arc.heated_percentage > 0 && (
                  <span className="text-xs text-orange-500">
                    <Zap className="inline h-3 w-3 mr-0.5" />
                    {data.emotional_arc.heated_percentage.toFixed(0)}% heated
                  </span>
                )}
              </div>

              {/* Dominant emotions */}
              <div className="flex flex-wrap gap-2">
                {data.emotional_arc.dominant_emotions.map((emotion) => (
                  <span key={emotion} className="inline-flex items-center gap-1 px-2 py-1 bg-muted rounded-full text-xs">
                    <span>{getEmotionEmoji(emotion)}</span>
                    <span className="capitalize">{emotion}</span>
                  </span>
                ))}
              </div>

              {/* Emotional journey */}
              <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                {data.emotional_arc.emotional_journey}
              </p>
            </div>
          )}

          {/* Timeline heatmap */}
          <div>
            <h4 className="text-xs font-medium text-muted-foreground mb-2">Emotional Timeline</h4>
            <SentimentTimeline
              windows={data.time_windows}
              onWindowClick={handleWindowClick}
            />
          </div>

          {/* Hot Moments */}
          {data.emotional_arc && data.emotional_arc.peak_moments.length > 0 && (
            <div>
              <button
                onClick={() => setShowHotMoments(!showHotMoments)}
                className="flex items-center gap-2 w-full text-left min-h-[36px]"
              >
                <Flame className="h-4 w-4 text-orange-500" />
                <span className="text-xs sm:text-sm font-medium flex-1">
                  Hot Moments ({data.emotional_arc.total_heated_segments})
                </span>
                <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${showHotMoments ? 'rotate-180' : ''}`} />
              </button>

              {showHotMoments && (
                <div className="mt-2 space-y-2">
                  {data.emotional_arc.peak_moments.map((moment, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleMomentClick(moment.timestamp)}
                      className="w-full text-left p-2 sm:p-3 bg-muted hover:bg-muted/80 rounded-lg transition-colors"
                    >
                      <div className="flex items-start gap-2">
                        <span className="flex items-center gap-1 text-xs text-orange-500 font-medium whitespace-nowrap">
                          <Clock className="h-3 w-3" />
                          {formatTime(moment.timestamp)}
                        </span>
                        <span className="flex-1 text-xs sm:text-sm line-clamp-2">
                          {moment.description}
                        </span>
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          {(moment.heat_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Re-analyze button */}
          <Button
            onClick={handleAnalyze}
            disabled={loading}
            variant="outline"
            className="w-full h-9"
            size="sm"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                <span className="text-xs">Re-analyzing...</span>
              </>
            ) : (
              <>
                <Flame className="mr-2 h-3 w-3" />
                <span className="text-xs">Re-analyze</span>
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  )
}
