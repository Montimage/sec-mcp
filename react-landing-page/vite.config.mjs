import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/sec-mcp/', // Base path for GitHub Pages deployment
  server: {
    port: 3000,
  },
  build: {
    outDir: 'dist',
  },
});