# Submission Checklist

## Required Submission Assets

- [ ] Revoke the API key previously visible in a terminal screenshot and update Vercel
- [ ] Public or reviewer-accessible repository
- [x] Online demo URL: https://emoti-gotchi.vercel.app
- [ ] Demo video under 5 minutes
- [x] README
- [x] Technical report
- [x] Deployment guide
- [x] Edge feasibility document
- [x] Judging alignment document
- [x] Online QA document
- [x] Final judging-aligned demo video script
- [x] Final submission audit

## Local Verification

Run these before final submission:

```bash
bun install
bun run gemma:test
bun run edge:sim
bun run build
```

Expected:

- `gemma:test` reaches `gemma-4-26b-a4b-it`
- `edge:sim` prints hardware feasibility table
- `build` completes without TypeScript or bundling errors

## Demo Flow Check

- [x] Open demo URL in a private browser window
- [ ] Run normal sharing example
- [ ] Run hidden distress example
- [ ] Run anger/frustration example
- [ ] Run high-risk escalation example
- [ ] Confirm guardian consent modal opens only when requested
- [ ] Confirm anger maps to `validate_and_contain`
- [ ] Confirm high-risk remains gentle on child side and alerts only the guardian side
- [ ] Save a de-identified demo event
- [ ] Confirm Family Climate hides exact events, counts, child behavior, and evidence IDs
- [ ] Run `Gemma 4 Family Climate Outlook`
- [ ] Confirm the outlook contains one environment adjustment and uncertainty
- [ ] Confirm professional support handoff requires explicit guardian authorization
- [ ] Confirm edge response remains immediate while Family Climate runs
- [ ] Confirm no API key appears in browser, terminal, screenshots, or video

## Environment Variables

Local `.env.local`:

```env
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemma-4-26b-a4b-it
ALL_PROXY=socks5://127.0.0.1:1080
```

Production provider:

```env
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemma-4-26b-a4b-it
```

Do not set `ALL_PROXY` in production unless the provider requires a proxy.

## Claims To Make

Safe claims:

- The web demo runs with a real Gemma 4 Family Climate adapter over de-identified structured history.
- Realtime child-facing response is designed for Gemma 4 E2B edge deployment.
- Emoti-Gotchi is a privacy-first edge emotional support system, not a general AI toy.
- The current edge path is a simulation with transparent feasibility telemetry.
- Safety escalation is deterministic and independent from model output.
- Raw audio is intended to remain local in the production architecture.

Do not claim:

- Real Raspberry Pi E2B benchmark has been completed.
- The product diagnoses or treats mental health conditions.
- Cloud Gemma is used as the sole realtime child response path.

## Final Video Outline

1. Problem and target users.
2. Realtime E2B edge response.
3. Hidden distress correction.
4. Rules baseline vs Gemma reasoning.
5. Safety escalation and guardian consent.
6. Cloud Family Climate, privacy boundary, uncertainty, and authorized professional handoff.
7. Privacy and deployment roadmap.
