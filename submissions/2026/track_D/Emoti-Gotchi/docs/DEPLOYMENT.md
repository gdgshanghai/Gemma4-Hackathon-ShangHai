# Deployment Guide

## Current Status

The project is ready for hosted demo deployment once a provider account is available. The app uses TanStack Start server functions, so the deployment target must support server-side runtime or serverless functions.

Current local verification:

- real Gemma 4 cloud review adapter: `gemma-4-26b-a4b-it`
- realtime E2B edge path: simulated
- deterministic safety audit: implemented
- documentation: complete for submission draft

Production demo:

- https://emoti-gotchi.vercel.app

## Environment Variables

Local `.env.local`:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemma-4-26b-a4b-it
ALL_PROXY=socks5://127.0.0.1:1080
```

Production:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemma-4-26b-a4b-it
```

Do not expose `GEMINI_API_KEY` in frontend code or public deployment logs.

`ALL_PROXY` is only for local environments where the terminal cannot directly reach Google APIs.

## Local Verification

```bash
bun install
bun run gemma:test
bun run edge:sim
bun run build
```

Expected:

- `gemma:test` reaches the cloud model
- `edge:sim` prints feasibility estimates
- `build` completes

## Recommended Provider: Vercel

The project build is configured with Nitro's `vercel` preset in `vite.config.ts`, so the hosted demo keeps the server-side Gemma adapter instead of becoming a static-only page.

### Option A: Vercel CLI prebuilt upload

Use this when you want the fastest manual upload from the current machine.

```powershell
# Run this inside the Emoti-Gotchi_ui-demo project folder.
bun run build
cd dist
bunx vercel login
bunx vercel deploy --prebuilt
```

For the final public URL, run:

```powershell
bunx vercel deploy --prebuilt --prod
```

Set these environment variables in the Vercel project before testing Gemma cloud review:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemma-4-26b-a4b-it
```

Do not set `ALL_PROXY` in Vercel unless the hosted runtime specifically needs it. It is only for local network access.

### Option B: GitHub import

1. Push the repository to GitHub.
2. Import the repository in Vercel.
3. Confirm the build command is `bun run build`.
4. Set environment variables:
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL=gemma-4-26b-a4b-it`
5. Deploy.
6. Open the URL in a private browser and run the checklist in `docs/SUBMISSION_CHECKLIST.md`.

## Netlify Option

Use only if the TanStack Start server function output works in the selected Netlify runtime.

1. Push repo to GitHub.
2. Import repo in Netlify.
3. Add environment variables.
4. Build with `bun run build`.
5. Confirm server functions work by running `Gemma 4 Cloud Review`.

## Cloudflare Pages Option

Use only if the TanStack Start output is configured for Cloudflare-compatible runtime.

1. Import repo.
2. Add environment variables.
3. Build with `bun run build`.
4. Confirm server function access to Google API.

## Demo Honesty Notes

Say:

- real Gemma 4 cloud review is connected
- realtime child response is designed for E2B edge
- current E2B path is a simulation with visible telemetry
- cloud review is intentionally slower and parent-facing

Do not say:

- the model already runs on Raspberry Pi
- the product diagnoses children
- cloud Gemma is the only realtime child response

## Production Hardening Later

Before a real pilot:

- add rate limits to the model endpoint
- add audit log redaction
- add child-safety professional review
- use consented audio data only
- perform Raspberry Pi or mobile edge benchmark
- add encryption and guardian account controls
