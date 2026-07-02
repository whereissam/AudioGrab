import { browser, storage } from '#imports';
import { detectPlatform, type PlatformMatch } from '../../utils/platforms';
import {
  buildAddUrl,
  DEFAULT_SERVER,
  normalizeServerUrl,
  originPattern,
  type CaptureAction,
} from '../../utils/server';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const statusEl = $<HTMLDivElement>('status');
const statusTextEl = $<HTMLSpanElement>('status-text');
const urlDisplayEl = $<HTMLDivElement>('url-display');
const transcribeBtn = $<HTMLButtonElement>('transcribe-btn');
const downloadBtn = $<HTMLButtonElement>('download-btn');
const messageEl = $<HTMLDivElement>('message');
const serverUrlInput = $<HTMLInputElement>('server-url');
const apiKeyInput = $<HTMLInputElement>('api-key');
const saveBtn = $<HTMLButtonElement>('save-btn');
const openUiLink = $<HTMLAnchorElement>('open-ui');

let currentUrl = '';
let currentMatch: PlatformMatch | null = null;
let serverUrl = DEFAULT_SERVER;
let apiKey = '';

async function init() {
  serverUrl = normalizeServerUrl((await storage.getItem<string>('sync:serverUrl')) || DEFAULT_SERVER);
  apiKey = (await storage.getItem<string>('sync:apiKey')) || '';
  serverUrlInput.value = serverUrl;
  apiKeyInput.value = apiKey;
  openUiLink.href = serverUrl;

  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  currentUrl = tab?.url || '';
  currentMatch = detectPlatform(currentUrl);

  if (currentMatch) {
    statusEl.className = 'status supported';
    statusTextEl.textContent = `Supported: ${currentMatch.name}`;
    urlDisplayEl.textContent = currentUrl;
    urlDisplayEl.hidden = false;
    transcribeBtn.disabled = false;
    downloadBtn.disabled = false;
  } else {
    statusEl.className = 'status unsupported';
    statusTextEl.textContent = 'Not a supported page';
    transcribeBtn.disabled = true;
    downloadBtn.disabled = true;
  }
}

function showMessage(text: string, isError = false) {
  messageEl.textContent = text;
  messageEl.className = `message ${isError ? 'error' : 'success'}`;
  messageEl.hidden = false;
  setTimeout(() => (messageEl.hidden = true), 5000);
}

/** Ensure we hold host permission for the (possibly remote) server origin. */
async function ensureServerPermission(): Promise<boolean> {
  const origins = [originPattern(serverUrl)];
  if (await browser.permissions.contains({ origins })) return true;
  try {
    return await browser.permissions.request({ origins });
  } catch {
    return false;
  }
}

async function sendToServer(action: CaptureAction) {
  if (!currentUrl || !currentMatch) return;

  if (!(await ensureServerPermission())) {
    showMessage(`Permission to reach ${serverUrl} was denied.`, true);
    return;
  }

  try {
    const headers: Record<string, string> = {};
    if (apiKey) headers['X-API-Key'] = apiKey;

    const response = await fetch(buildAddUrl(serverUrl, currentUrl, action), { headers });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    const data = await response.json();
    showMessage(`Added to queue! Job ${data.job_id}`);
    await browser.tabs.create({ url: serverUrl });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    if (msg.includes('Failed to fetch')) {
      showMessage(`Cannot connect to ${serverUrl}. Is Sift running?`, true);
    } else {
      showMessage(msg, true);
    }
  }
}

transcribeBtn.addEventListener('click', () => sendToServer('transcribe'));
downloadBtn.addEventListener('click', () => sendToServer('download'));

saveBtn.addEventListener('click', async () => {
  serverUrl = normalizeServerUrl(serverUrlInput.value);
  apiKey = apiKeyInput.value.trim();
  await storage.setItems([
    { key: 'sync:serverUrl', value: serverUrl },
    { key: 'sync:apiKey', value: apiKey },
  ]);
  openUiLink.href = serverUrl;
  await ensureServerPermission();
  showMessage('Settings saved!');
});

openUiLink.addEventListener('click', (e) => {
  e.preventDefault();
  browser.tabs.create({ url: serverUrl });
});

init();
