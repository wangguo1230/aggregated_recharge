import { fileURLToPath, URL } from 'node:url';
import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

// 默认转发到独立的 AskWhy 后端（askwhy-center，端口 18424）。
const apiTarget = process.env.VITE_ASKWHY_API_TARGET || 'http://127.0.0.1:18424';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': apiTarget,
    },
  },
});
