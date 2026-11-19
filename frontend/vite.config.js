import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 900 },
  server: { proxy: { '/api': process.env.API_URL || 'http://localhost:8000' } },
});
