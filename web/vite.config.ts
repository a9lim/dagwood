import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vite';

// The built bundle is emitted into the Python package so `dag serve` can serve
// it as static files. In dev (`npm run dev`), proxy the API + websocket to a
// running dagwood server on port 8765.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: '../src/dagwood/live/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8765',
      '/ws': { target: 'ws://127.0.0.1:8765', ws: true },
    },
  },
});
