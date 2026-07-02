// Server-communication helpers (pure where possible so they can be unit-tested).

export const DEFAULT_SERVER = 'http://localhost:8000';

export type CaptureAction = 'download' | 'transcribe';

/** Trim whitespace and any trailing slashes from a server URL. */
export function normalizeServerUrl(input: string): string {
  return input.trim().replace(/\/+$/, '');
}

/** Build the quick-add URL hitting the server's GET /api/add endpoint. */
export function buildAddUrl(serverUrl: string, pageUrl: string, action: CaptureAction): string {
  const params = new URLSearchParams({ url: pageUrl, action });
  return `${normalizeServerUrl(serverUrl)}/api/add?${params.toString()}`;
}

/** Derive the `<origin>/*` match pattern used to request host permission. */
export function originPattern(serverUrl: string): string {
  const { origin } = new URL(normalizeServerUrl(serverUrl));
  return `${origin}/*`;
}
