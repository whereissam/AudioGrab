import { describe, expect, it } from 'vitest';
import { buildAddUrl, normalizeServerUrl, originPattern } from './server';

describe('normalizeServerUrl', () => {
  it('trims whitespace and trailing slashes', () => {
    expect(normalizeServerUrl('  http://localhost:8000/  ')).toBe('http://localhost:8000');
    expect(normalizeServerUrl('http://localhost:8000///')).toBe('http://localhost:8000');
    expect(normalizeServerUrl('https://sift.example.com')).toBe('https://sift.example.com');
  });
});

describe('buildAddUrl', () => {
  it('builds an encoded /api/add URL', () => {
    const url = buildAddUrl('http://localhost:8000/', 'https://youtu.be/abc?x=1', 'download');
    expect(url).toBe(
      'http://localhost:8000/api/add?url=https%3A%2F%2Fyoutu.be%2Fabc%3Fx%3D1&action=download',
    );
  });

  it('supports the transcribe action', () => {
    expect(buildAddUrl('http://localhost:8000', 'https://x.com/a/status/1', 'transcribe')).toContain(
      'action=transcribe',
    );
  });
});

describe('originPattern', () => {
  it('derives an <origin>/* match pattern', () => {
    expect(originPattern('https://sift.example.com/path/')).toBe('https://sift.example.com/*');
    expect(originPattern('http://192.168.1.5:8000')).toBe('http://192.168.1.5:8000/*');
  });
});
