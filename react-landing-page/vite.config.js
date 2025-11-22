import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/sec-mcp/', // Base path for GitHub Pages deployment
  server: {
    port: 3000,
  },
  build: {
    outDir: 'dist',
  },
});
