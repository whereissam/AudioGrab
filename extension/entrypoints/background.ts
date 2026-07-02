import { defineBackground, browser, storage } from '#imports';
import { DEFAULT_SERVER } from '../utils/server';

// The background worker only manages the toolbar badge (per-tab) and seeds the
// default server URL on install. All detection logic lives in the content
// script; the badge reflects the messages it sends.
export default defineBackground(() => {
  browser.runtime.onMessage.addListener((message: any, sender) => {
    const tabId = sender.tab?.id;
    if (tabId === undefined) return;

    if (message?.type === 'PAGE_SUPPORTED') {
      browser.action.setBadgeText({ text: '!', tabId });
      browser.action.setBadgeBackgroundColor({ color: '#6366f1', tabId });
    } else if (message?.type === 'PAGE_UNSUPPORTED') {
      browser.action.setBadgeText({ text: '', tabId });
    }
  });

  browser.runtime.onInstalled.addListener(async (details) => {
    if (details.reason === 'install') {
      await storage.setItem('sync:serverUrl', DEFAULT_SERVER);
    }
  });
});
