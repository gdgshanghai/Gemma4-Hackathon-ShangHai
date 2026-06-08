import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
export default defineConfig({
    plugins: [
        react(),
        VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['icons/u2.svg'],
            manifest: {
                name: 'U2 健康支持',
                short_name: 'U2',
                description: '匿名、本地优先的 HIV 心理健康与健康支持工具',
                theme_color: '#f5f3ed',
                background_color: '#f5f3ed',
                display: 'standalone',
                start_url: '/',
                icons: [
                    {
                        src: '/icons/u2.svg',
                        sizes: 'any',
                        type: 'image/svg+xml',
                        purpose: 'any maskable'
                    }
                ]
            },
            workbox: {
                navigateFallback: '/index.html',
                globPatterns: ['**/*.{js,css,html,svg,json}'],
                runtimeCaching: [
                    {
                        urlPattern: /^https:\/\/huggingface\.co\//,
                        handler: 'CacheFirst',
                        options: {
                            cacheName: 'u2-model-assets',
                            expiration: { maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 90 }
                        }
                    }
                ]
            }
        })
    ],
    worker: { format: 'es' },
    test: {
        environment: 'jsdom',
        setupFiles: ['./src/test/setup.ts']
    }
});
