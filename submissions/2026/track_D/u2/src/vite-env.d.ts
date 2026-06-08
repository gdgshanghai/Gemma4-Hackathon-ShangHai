/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_NEWS_WORKER_URL?: string
  readonly VITE_GEMMA_MODEL_SOURCE?: 'remote' | 'bundled'
  readonly VITE_GEMMA_MODEL_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
/// <reference types="vite-plugin-pwa/client" />

interface ImportMetaEnv {
  readonly VITE_NEWS_API_ENDPOINT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
