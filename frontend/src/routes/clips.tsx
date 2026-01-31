import { createFileRoute } from '@tanstack/react-router'
import { ClipsPage } from '@/components/clips/ClipsPage'

export const Route = createFileRoute('/clips')({
  component: ClipsRoute,
})

function ClipsRoute() {
  return (
    <div className="flex-1 flex items-center justify-center p-3 sm:p-4">
      <div className="w-full max-w-xl">
        <div className="bg-card rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
          <ClipsPage />
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Generate viral clips from your transcriptions
        </p>
      </div>
    </div>
  )
}
