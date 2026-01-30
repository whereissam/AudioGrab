import { createFileRoute, Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AISettings } from '@/components/settings/AISettings'

export const Route = createFileRoute('/settings')({
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted">
      <div className="max-w-4xl mx-auto p-4 sm:p-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Settings</h1>
            <p className="text-sm text-muted-foreground">
              Configure your application preferences
            </p>
          </div>
        </div>

        {/* Content */}
        <Tabs defaultValue="ai" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="ai">AI Provider</TabsTrigger>
            <TabsTrigger value="general">General</TabsTrigger>
          </TabsList>

          <TabsContent value="ai">
            <AISettings />
          </TabsContent>

          <TabsContent value="general">
            <div className="bg-card rounded-xl shadow-lg p-6">
              <h2 className="text-lg font-semibold text-foreground mb-4">General Settings</h2>
              <p className="text-muted-foreground text-sm">
                General settings will be available in a future update.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
