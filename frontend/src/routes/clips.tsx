import { createFileRoute } from '@tanstack/react-router'
import { ClipsPage } from '@/components/clips/ClipsPage'

export const Route = createFileRoute('/clips')({
  component: ClipsRoute,
})

function ClipsRoute() {
  return (
    <div className="bg-card rounded-xl shadow-lg p-4 sm:p-6 md:p-8">
      <ClipsPage />
    </div>
  )
}
