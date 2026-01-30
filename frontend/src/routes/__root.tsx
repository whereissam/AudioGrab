import { createRootRoute, Outlet, Link, useLocation } from '@tanstack/react-router'
import { ThemeToggle } from '@/components/theme-toggle'
import { Rss } from 'lucide-react'

export const Route = createRootRoute({
  component: () => {
    const location = useLocation()
    const isHome = location.pathname === '/'

    return (
      <>
        {/* Top bar */}
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2">
          {isHome && (
            <Link
              to="/subscriptions"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-card border shadow-sm hover:bg-muted transition-colors text-sm font-medium text-foreground"
            >
              <Rss className="h-4 w-4" />
              <span className="hidden sm:inline">Subscriptions</span>
            </Link>
          )}
          <ThemeToggle />
        </div>
        <Outlet />
      </>
    )
  },
})
