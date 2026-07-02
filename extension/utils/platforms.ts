// Single source of truth for platform detection, shared by the content script,
// the popup, and the generated content-script `matches`. Keep in sync with the
// server's DownloaderFactory (app/core/platforms/).

export interface PlatformMatch {
  /** Server platform id (matches app/core/base.py Platform enum values). */
  type: string;
  /** Human-friendly label shown in the popup. */
  name: string;
}

interface PlatformPattern extends PlatformMatch {
  pattern: RegExp;
}

// Order matters: more specific patterns (e.g. X Spaces) before generic ones.
export const PLATFORM_PATTERNS: PlatformPattern[] = [
  { pattern: /x\.com\/i\/spaces\//i, type: 'x_spaces', name: 'X Space' },
  { pattern: /twitter\.com\/i\/spaces\//i, type: 'x_spaces', name: 'X Space' },
  { pattern: /(?:x|twitter)\.com\/\w+\/status\//i, type: 'x_video', name: 'X Video' },
  { pattern: /youtube\.com\/watch\?v=/i, type: 'youtube', name: 'YouTube' },
  { pattern: /youtube\.com\/shorts\//i, type: 'youtube', name: 'YouTube Shorts' },
  { pattern: /youtu\.be\//i, type: 'youtube', name: 'YouTube' },
  { pattern: /music\.youtube\.com\/watch\?v=/i, type: 'youtube', name: 'YouTube Music' },
  { pattern: /podcasts\.apple\.com\/.*\/podcast\//i, type: 'apple_podcasts', name: 'Apple Podcast' },
  { pattern: /open\.spotify\.com\/episode\//i, type: 'spotify', name: 'Spotify Episode' },
  { pattern: /xiaoyuzhoufm\.com\/episode\//i, type: 'xiaoyuzhou', name: '小宇宙 Episode' },
  { pattern: /ximalaya\.com\/sound\/\d+/i, type: 'ximalaya', name: '喜马拉雅 Episode' },
  { pattern: /xiaohongshu\.com\/explore\//i, type: 'xiaohongshu', name: '小红书 Post' },
  { pattern: /xhslink\.com\//i, type: 'xiaohongshu', name: '小红书 Post' },
  { pattern: /instagram\.com\/(?:reel|reels|p|tv)\//i, type: 'instagram', name: 'Instagram' },
];

/** Return the first matching platform for a URL, or null if unsupported. */
export function detectPlatform(url: string): PlatformMatch | null {
  for (const p of PLATFORM_PATTERNS) {
    if (p.pattern.test(url)) {
      return { type: p.type, name: p.name };
    }
  }
  return null;
}

// Host match patterns for the content script (derived so they can't drift from
// the detection list above). Broad per-host; precise URL matching happens in
// detectPlatform() at runtime.
export const CONTENT_MATCHES: string[] = [
  '*://x.com/*',
  '*://twitter.com/*',
  '*://*.youtube.com/*',
  '*://youtube.com/*',
  '*://youtu.be/*',
  '*://podcasts.apple.com/*',
  '*://open.spotify.com/*',
  '*://*.xiaoyuzhoufm.com/*',
  '*://*.ximalaya.com/*',
  '*://*.xiaohongshu.com/*',
  '*://xhslink.com/*',
  '*://*.instagram.com/*',
];
