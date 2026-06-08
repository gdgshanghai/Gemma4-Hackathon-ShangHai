import path from "node:path"
import { defineConfig } from "vitest/config"

// store/纯逻辑单测跑在 node 环境。复用 vite 的 @ alias；setup 注入内存版 localStorage
//（node 25 自带的 localStorage 残缺，见 vitest.setup.ts）。
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
})
