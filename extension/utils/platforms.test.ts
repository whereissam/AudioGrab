import { describe, expect, it } from 'vitest';
import { detectPlatform } from './platforms';

describe('detectPlatform', () => {
  it.each([
    ['https://x.com/i/spaces/1vOxwdyYrlqKB', 'x_spaces'],
    ['https://twitter.com/i/spaces/abc', 'x_spaces'],
    ['https://x.com/SpaceX/status/2072695632104468543', 'x_video'],
    ['https://www.youtube.com/watch?v=I-PMiyYZkrs', 'youtube'],
    ['https://www.youtube.com/shorts/abc123', 'youtube'],
    ['https://youtu.be/I-PMiyYZkrs', 'youtube'],
    ['https://podcasts.apple.com/de/podcast/show/id123?i=456', 'apple_podcasts'],
    ['https://open.spotify.com/episode/abc123', 'spotify'],
    ['https://www.xiaoyuzhoufm.com/episode/6a4123349d2f5743683f2bd6', 'xiaoyuzhou'],
    ['https://www.ximalaya.com/sound/998052123', 'ximalaya'],
    ['https://www.xiaohongshu.com/explore/6a2417ff0000000006031044', 'xiaohongshu'],
    ['https://www.instagram.com/reel/DZKus9XB34d/', 'instagram'],
  ])('detects %s → %s', (url, type) => {
    expect(detectPlatform(url)?.type).toBe(type);
  });

  it('returns null for unsupported URLs', () => {
    expect(detectPlatform('https://example.com/page')).toBeNull();
    // A Ximalaya album page is not a single episode.
    expect(detectPlatform('https://www.ximalaya.com/waiyu/3240558/')).toBeNull();
  });

  it('X Spaces takes precedence over the generic status matcher', () => {
    expect(detectPlatform('https://x.com/i/spaces/123')?.type).toBe('x_spaces');
  });
});
