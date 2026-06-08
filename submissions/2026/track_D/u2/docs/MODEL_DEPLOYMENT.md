# Gemma 4 deployment modes

## Current Web/PWA mode

- Model: `onnx-community/gemma-4-E4B-it-ONNX`
- Runtime: Transformers.js in a Web Worker
- Device: desktop Chrome/Edge with WebGPU
- Weights: downloaded only after explicit user action and cached in the browser
- Fallback: deterministic safety templates and structured tools

The production JavaScript bundle contains the Transformers.js runtime and ONNX Runtime WASM. It does not contain Gemma weight files.

## Bundled web-asset mode

Run:

```bash
npm run model:prepare
VITE_GEMMA_MODEL_SOURCE=bundled npm run build
```

This places the model under `/models/`, disables remote model loading, and lets a PWA or Capacitor bundle ship the files as static assets.

## Mobile caveat

Shipping weights and running them are separate problems. Capacitor still executes the web app inside WKWebView or Android WebView. WebGPU availability, memory limits and large-asset packaging must be tested on real devices.

For a production mobile app, keep `LocalAIEngine` as the shared interface and add a native adapter. Candidate model assets:

- Web: `onnx-community/gemma-4-E4B-it-ONNX`
- Mobile exploration: `onnx-community/gemma-4-E4B-it-qat-mobile-ONNX`

The native adapter can later use a platform-supported ONNX or Google AI Edge runtime without changing the product pages or Agent orchestration layer.
