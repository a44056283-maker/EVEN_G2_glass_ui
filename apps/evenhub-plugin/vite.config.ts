import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
    proxy: {
      '/health': 'http://127.0.0.1:8787',
      '/vision': 'http://127.0.0.1:8787',
      '/ask': 'http://127.0.0.1:8787',
      '/tts': 'http://127.0.0.1:8787',
      '/transcribe': 'http://127.0.0.1:8787',
      '/asr': 'http://127.0.0.1:8787',
      '/memory': 'http://127.0.0.1:8787',
      '/trading': 'http://127.0.0.1:8787',
      '/openclaw': 'http://127.0.0.1:8787',
      '/audio': {
        target: 'ws://127.0.0.1:8787',
        ws: true,
      },
    },
  },
})
