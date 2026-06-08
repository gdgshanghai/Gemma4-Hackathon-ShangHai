import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), "");
	const apiTarget = (env.API_BASE_URL || "http://127.0.0.1:1234/v1").replace(/\/v1\/?$/, "");
	const apiKey = env.OPENAI_API_KEY || "";

	return {
		plugins: [react(), tailwindcss()],
		resolve: {
			alias: {
				"@": resolve(__dirname, "./src"),
			},
		},
		server: {
			port: 3000,
			proxy: {
				"/api/gamma": {
					target: "https://gamma-api.polymarket.com",
					changeOrigin: true,
					rewrite: (path) => path.replace(/^\/api\/gamma/, ""),
				},
				"/api/clob": {
					target: "https://clob.polymarket.com",
					changeOrigin: true,
					rewrite: (path) => path.replace(/^\/api\/clob/, ""),
				},
				"/api/gemma": {
					target: apiTarget,
					changeOrigin: true,
					rewrite: (path) => path.replace(/^\/api\/gemma/, ""),
					configure: (proxy) => {
						console.log(`[proxy] Gemma local/OpenAI-compatible ${apiTarget}`);
						proxy.on("proxyReq", (proxyReq) => {
							proxyReq.setHeader("Authorization", `Bearer ${apiKey || "local-gemma"}`);
						});
						proxy.on("error", (err, req) => {
							console.error(`[proxy] error on ${req.url}:`, err.message);
						});
					},
				},
			},
		},
	};
});
