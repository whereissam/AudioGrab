import { createFileRoute } from '@tanstack/react-router'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AISettings } from '@/components/settings/AISettings'
import { TranslationSettings } from '@/components/settings/TranslationSettings'

export const Route = createFileRoute('/settings')({
  component: SettingsPage,
})

function SettingsPage() {
  return (
    <div className="flex-1 py-6">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Configure your application preferences
          </p>
        </div>

        {/* Content */}
        <Tabs defaultValue="ai" className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-6">
            <TabsTrigger value="ai">AI Summary</TabsTrigger>
            <TabsTrigger value="translation">Translation</TabsTrigger>
            <TabsTrigger value="general">General</TabsTrigger>
          </TabsList>

          <TabsContent value="ai">
            <AISettings />
          </TabsContent>

          <TabsContent value="translation">
            <TranslationSettings />
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
