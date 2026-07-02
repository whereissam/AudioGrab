import { defineContentScript, browser } from '#imports';
import { CONTENT_MATCHES, detectPlatform } from '../utils/platforms';

// Detect supported media on the page and tell the background worker so it can
// badge the toolbar icon. SPA route changes (YouTube, X, Instagram) are caught
// by a cheap 1s href poll — deliberately NOT a full-subtree MutationObserver,
// which fired on every DOM mutation in the old extension.
export default defineContentScript({
  matches: CONTENT_MATCHES,
  runAt: 'document_idle',
  main() {
    const notify = () => {
      const platform = detectPlatform(location.href);
      browser.runtime
        .sendMessage({
          type: platform ? 'PAGE_SUPPORTED' : 'PAGE_UNSUPPORTED',
          platform,
          url: location.href,
        })
        .catch(() => {
          /* worker asleep / navigating away — safe to ignore */
        });
    };

    notify();

    let lastHref = location.href;
    setInterval(() => {
      if (location.href !== lastHref) {
        lastHref = location.href;
        notify();
      }
    }, 1000);
  },
});
