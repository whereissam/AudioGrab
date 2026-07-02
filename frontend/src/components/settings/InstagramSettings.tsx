import { Puzzle, LogIn, Download, FileCog, RefreshCw, Play, ShieldAlert, Check, ExternalLink } from 'lucide-react'

interface Step {
  icon: React.ComponentType<{ className?: string }>
  title: string
  body: React.ReactNode
}

const STEPS: Step[] = [
  {
    icon: Puzzle,
    title: 'Install the cookies add-on',
    body: (
      <>
        Add the free{' '}
        <span className="font-medium text-foreground">“Get cookies.txt LOCALLY”</span>{' '}
        extension to your browser. Open your browser&apos;s add-on store (Chrome Web Store or
        Firefox Add-ons), search that exact name, and click <span className="font-medium text-foreground">Add to browser</span>.
        <span className="mt-1.5 block text-xs">
          The word <span className="font-medium">LOCALLY</span> matters — that version keeps
          everything on your machine and never uploads it.
        </span>
      </>
    ),
  },
  {
    icon: LogIn,
    title: 'Open Instagram and log in',
    body: (
      <>
        Go to{' '}
        <a
          href="https://www.instagram.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 font-medium text-foreground underline decoration-pink-500/40 underline-offset-2 hover:decoration-pink-500"
        >
          instagram.com <ExternalLink className="h-3 w-3" />
        </a>{' '}
        and make sure you&apos;re signed in — you should see your normal feed.
      </>
    ),
  },
  {
    icon: Download,
    title: 'Export your cookies file',
    body: (
      <>
        With the Instagram tab open, click the <span className="font-medium text-foreground">cookies.txt</span>{' '}
        icon in your browser toolbar (it may be under the puzzle-piece{' '}
        <span className="font-medium text-foreground">Extensions</span> button), then click{' '}
        <span className="font-medium text-foreground">Export</span>. It saves a file named{' '}
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">www.instagram.com_cookies.txt</code>{' '}
        to your Downloads folder.
      </>
    ),
  },
  {
    icon: FileCog,
    title: 'Add the file path to your .env',
    body: (
      <>
        Open Sift&apos;s <code className="rounded bg-muted px-1.5 py-0.5 text-xs">.env</code>{' '}
        settings file (in the app&apos;s main folder) with any text editor and add one line
        pointing at the file you just saved:
        <span className="mt-2 block overflow-x-auto rounded-lg bg-zinc-900 p-3 font-mono text-xs leading-relaxed text-zinc-100">
          <span className="text-zinc-500"># Instagram login — your exported file&apos;s path</span>
          <br />
          <span className="text-amber-400">INSTAGRAM_COOKIES_FILE</span>
          <span className="text-zinc-400">=</span>
          <span className="text-emerald-300">/Users/you/Downloads/www.instagram.com_cookies.txt</span>
        </span>
        <span className="mt-1.5 block text-xs">
          Use your real path — on a Mac, right-click the file → <span className="font-medium">Get Info</span>;
          on Windows, Shift-right-click → <span className="font-medium">Copy as path</span>.
        </span>
      </>
    ),
  },
  {
    icon: RefreshCw,
    title: 'Restart Sift',
    body: <>Close and reopen the app so it picks up the new setting.</>,
  },
  {
    icon: Play,
    title: 'Paste a reel and download',
    body: (
      <>
        Drop any Instagram reel or post link into Sift and hit download — it should now save
        straight to your output folder. Reels, posts, and IGTV all work the same way from here.
      </>
    ),
  },
]

export function InstagramSettings() {
  return (
    <div className="bg-card rounded-xl shadow-lg p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2.5 mb-2">
          <span className="inline-grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-amber-400 via-pink-500 to-purple-600 text-white">
            <Download className="h-4 w-4" />
          </span>
          <h2 className="text-lg font-semibold text-foreground">Instagram Downloads</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          Instagram only serves videos to people who are logged in. Give Sift a copy of your
          login once — using a free browser add-on. No coding, about 3 minutes.
        </p>
      </div>

      {/* Steps */}
      <ol className="space-y-3">
        {STEPS.map((step, i) => {
          const Icon = step.icon
          return (
            <li
              key={i}
              className="relative flex gap-4 rounded-xl border border-border bg-background/40 p-4"
            >
              <div className="flex flex-col items-center gap-2">
                <span className="inline-grid h-8 w-8 flex-none place-items-center rounded-lg bg-gradient-to-br from-amber-400 via-pink-500 to-purple-600 text-sm font-bold tabular-nums text-white">
                  {i + 1}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 flex-none text-muted-foreground" />
                  <h3 className="font-medium text-foreground">{step.title}</h3>
                </div>
                <p className="mt-1.5 text-sm text-muted-foreground">{step.body}</p>
              </div>
            </li>
          )
        })}
      </ol>

      {/* Success note */}
      <div className="flex items-center gap-3 rounded-lg border border-green-500/20 bg-green-500/10 p-4 text-sm text-green-700 dark:text-green-400">
        <Check className="h-5 w-5 flex-none" />
        <span>
          <span className="font-semibold">That&apos;s it.</span> Once configured, Instagram
          downloads work just like YouTube and X.
        </span>
      </div>

      {/* Security warning */}
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-300">
        <ShieldAlert className="h-5 w-5 flex-none mt-0.5" />
        <div>
          <span className="block font-semibold">Keep this file private</span>
          It contains your Instagram login — anyone who has it can access your account. Don&apos;t
          share it or commit it to git. If downloads start failing again with a “requires login”
          message weeks later, your session simply expired: repeat steps 3–4 for a fresh file.
        </div>
      </div>
    </div>
  )
}
