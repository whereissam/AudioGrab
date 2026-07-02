import { defineConfig } from 'wxt';

// One config → Chrome (MV3) and Firefox manifests are generated automatically.
export default defineConfig({
  manifest: {
    name: 'Sift',
    description:
      'Download and transcribe audio/video from X Spaces, YouTube, podcasts, 小宇宙, 喜马拉雅, 小红书, Instagram, and more',
    permissions: ['activeTab', 'storage'],
    // Default local server works with no prompt. A user-configured remote
    // server origin is requested at runtime (see utils/server.ts), which fixes
    // the old hardcoded-localhost limitation.
    host_permissions: ['http://localhost:8000/*', 'http://127.0.0.1:8000/*'],
    optional_host_permissions: ['*://*/*'],
    browser_specific_settings: {
      gecko: { id: 'sift@gaib.ai', strict_min_version: '109.0' },
    },
  },
});
