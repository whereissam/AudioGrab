import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Menu, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTheme } from '@/components/theme-provider'

export function MobileNav() {
  const [isOpen, setIsOpen] = useState(false)
  const { theme } = useTheme()
  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)

  return (
    <div className="sm:hidden">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        className="h-11 w-11"
      >
        {isOpen ? (
          <X className="h-5 w-5" />
        ) : (
          <Menu className="h-5 w-5" />
        )}
        <span className="sr-only">Toggle menu</span>
      </Button>

      {isOpen && (
        <div className={`absolute top-16 left-0 right-0 shadow-xl z-50 border-b ${isDark ? 'bg-background border-border' : 'bg-background border-border'}`}>
          <div className="container mx-auto px-4 py-2">
            <div className="flex flex-col">
              <Link
                to="/"
                className="text-foreground hover:text-primary [&.active]:text-primary [&.active]:font-medium transition-colors py-3 min-h-[48px] flex items-center"
                onClick={() => setIsOpen(false)}
              >
                Home
              </Link>
              <Link
                to="/about"
                className="text-foreground hover:text-primary [&.active]:text-primary [&.active]:font-medium transition-colors py-3 min-h-[48px] flex items-center"
                onClick={() => setIsOpen(false)}
              >
                About
              </Link>
              <Link
                to="/features"
                className="text-foreground hover:text-primary [&.active]:text-primary [&.active]:font-medium transition-colors py-3 min-h-[48px] flex items-center"
                onClick={() => setIsOpen(false)}
              >
                Features
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}