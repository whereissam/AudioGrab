import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { LiveTranscriber } from '@/components/live'

export const Route = createFileRoute('/live')({
  component: LiveTranscriptionPage,
})

function LiveTranscriptionPage() {
  return (
    <div className="flex-1 py-6">
      <div className="max-w-3xl mx-auto px-4">
        {/* Header with back link */}
        <div className="mb-6">
          <Link
            to="/transcribe"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Transcribe
          </Link>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
            Live Transcription
          </h1>
          <p className="text-muted-foreground mt-2">
            Transcribe audio from your microphone in real-time
          </p>
        </div>

        {/* Main transcriber component */}
        <LiveTranscriber />

        {/* Usage tips */}
        <div className="mt-8 p-4 bg-muted/50 rounded-lg">
          <h3 className="font-medium text-foreground mb-2">Tips for best results</h3>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li>Use a good quality microphone in a quiet environment</li>
            <li>Speak clearly at a moderate pace</li>
            <li>For longer recordings, the "base" or "small" model offers a good balance</li>
            <li>Select your language manually for better accuracy if known</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
