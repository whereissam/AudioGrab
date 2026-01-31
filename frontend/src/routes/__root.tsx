import { createRootRoute, Outlet, Link, useLocation } from '@tanstack/react-router'
import { ThemeToggle } from '@/components/theme-toggle'
import { FileAudio, FileVideo, FileText, Scissors, Rss, Settings } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/audio', label: 'Audio', icon: FileAudio },
  { to: '/video', label: 'Video', icon: FileVideo },
  { to: '/transcribe', label: 'Transcribe', icon: FileText },
  { to: '/clips', label: 'Clips', icon: Scissors },
] as const

export const Route = createRootRoute({
  component: () => {
    const location = useLocation()

    return (
      <div className="min-h-screen bg-gradient-to-br from-background to-muted flex flex-col">
        {/* Header */}
        <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-sm border-b">
          <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
            {/* Logo */}
            <Link to="/audio" className="flex items-center gap-2">
              <img src="/logo.svg" alt="AudioGrab" className="h-8 w-auto" />
              <span className="font-bold text-lg text-foreground hidden sm:inline">AudioGrab</span>
            </Link>

            {/* Main Navigation */}
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location.pathname === to
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{label}</span>
                </Link>
              ))}
            </nav>

            {/* Right side */}
            <div className="flex items-center gap-2">
              <Link
                to="/subscriptions"
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === '/subscriptions'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <Rss className="h-4 w-4" />
                <span className="hidden lg:inline">Subscriptions</span>
              </Link>
              <Link
                to="/settings"
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === '/settings'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <Settings className="h-4 w-4" />
                <span className="hidden lg:inline">Settings</span>
              </Link>
              <ThemeToggle />
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 flex flex-col">
          <Outlet />
        </main>
      </div>
    )
  },
})
