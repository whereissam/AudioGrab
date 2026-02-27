import { createRootRoute, Outlet, Link, useLocation } from '@tanstack/react-router'
import { ThemeToggle } from '@/components/theme-toggle'
import { FileAudio, FileVideo, FileText, Scissors, Rss, Settings, Mic } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/audio', label: 'Audio', icon: FileAudio },
  { to: '/video', label: 'Video', icon: FileVideo },
  { to: '/transcribe', label: 'Transcribe', icon: FileText },
  { to: '/clips', label: 'Clips', icon: Scissors },
  { to: '/live', label: 'Live', icon: Mic },
] as const

export const Route = createRootRoute({
  component: () => {
    const location = useLocation()
    const isMainPage = ['/audio', '/video', '/transcribe', '/clips', '/'].includes(location.pathname)

    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex flex-col">
        {/* Top right controls */}
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2">
          {isMainPage && (
            <>
              <Link
                to="/subscriptions"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-card border shadow-sm hover:bg-muted transition-colors text-sm font-medium text-foreground"
              >
                <Rss className="h-4 w-4" />
                <span className="hidden sm:inline">Subscriptions</span>
              </Link>
              <Link
                to="/settings"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-card border shadow-sm hover:bg-muted transition-colors text-sm font-medium text-foreground"
              >
                <Settings className="h-4 w-4" />
                <span className="hidden sm:inline">Settings</span>
              </Link>
            </>
          )}
          <ThemeToggle />
        </div>

        {/* Main content */}
        {isMainPage ? (
          <div className="flex-1 flex items-center justify-center p-3 sm:p-4">
            <div className="w-full max-w-xl">
              {/* Header */}
              <div className="text-center mb-6 sm:mb-8">
                <div className="flex justify-center mb-3 sm:mb-4">
                  <img src="/logo.svg" alt="AudioGrab" className="h-12 sm:h-16 w-auto" />
                </div>
                <h1 className="text-2xl sm:text-4xl font-bold text-foreground mb-1 sm:mb-2">AudioGrab</h1>
                <p className="text-sm sm:text-base text-muted-foreground">Download audio and video from your favorite platforms</p>
              </div>

              {/* Navigation Tabs */}
              <div className="grid w-full grid-cols-5 mb-4 h-11 sm:h-10 bg-muted rounded-lg p-1">
                {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                  <Link
                    key={to}
                    to={to}
                    className={`flex items-center justify-center gap-1 sm:gap-2 text-xs sm:text-sm rounded-md transition-all ${
                      location.pathname === to
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span className="hidden sm:inline">{label}</span>
                  </Link>
                ))}
              </div>

              {/* Page Content */}
              <Outlet />

              <p className="text-center text-xs text-muted-foreground mt-6">
                Supports public content with replay/download enabled
              </p>
            </div>
          </div>
        ) : (
          <Outlet />
        )}
      </div>
    )
  },
})
