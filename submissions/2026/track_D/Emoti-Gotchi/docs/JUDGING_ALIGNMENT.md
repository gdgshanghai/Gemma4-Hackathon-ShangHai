# Judging Alignment

This document maps Emoti-Gotchi to the Gemma 4 Developer Competition 2026 judging dimensions.

## 1. Real-World Impact - 30%

Evidence in project:

- Targets children aged 6-8 and their parents.
- Grounds the social problem in an East Asian family context: children may under-express distress, while guardians may default to correction, advice, or lecturing before emotional validation.
- Uses the early primary-school window as a prevention-oriented communication opportunity, not as a medical claim.
- Addresses hidden distress, parent-child communication gaps, and early prevention.
- Uses emotional weather to translate a complex support need into one understandable guardian response, instead of exposing behavior tracking, exact event counts, or raw transcripts.
- Uses a family-climate view to show recurring time and environment conditions, not to judge the child.
- High-risk signals first alert the guardian; a vetted professional-support referral requires explicit guardian consent.
- Provides a scalable path from web demo to edge hardware.
- Uses evidence-informed design references: child emotion understanding, parent emotion socialization, UNICEF child AI guidance, WHO AI ethics, and NIST AI RMF.

Demo proof:

- Parent card shows a seven-day family climate, settling index, broad time window, and one environment adjustment.
- Safety route shows immediate guardian steps followed by consent before any professional referral, instead of automatic external escalation.
- README and technical report state the product is not a medical diagnosis tool.

Remaining improvement:

- Add expert interview, school counselor feedback, or parent survey if time allows.
- Conduct independent child-safety expert review before any real child pilot.

## 2. Technical Excellence - 25%

Evidence in project:

- Real Gemma 4 Family Climate Outlook using `gemma-4-26b-a4b-it`.
- Cloud input restricted to de-identified structured family events.
- Evidence-linked output with uncertainty and `insufficient_data` handling.
- Server-side API key handling through environment variables.
- Structured output schema for emotional state, hardware action, and parent guidance.
- Deterministic P0 safety audit independent from the model.
- E2B edge simulation with latency, memory, confidence, and schema telemetry.
- Local proxy support for development environments that cannot directly reach Google APIs.

Demo proof:

- Trace panel displays model/runtime/schema telemetry.
- Gemma JSON panel exposes constrained hardware output.
- Technical Proof compares Rules, Gemma 4 E2B, and an on-demand real Cloud benchmark on the same synthetic scene.
- Safety coverage matrix shows where Gemma adds contextual value without replacing deterministic escalation.
- `bun run gemma:test` verifies cloud adapter connectivity.
- `bun run edge:sim` verifies hardware budget assumptions.

Remaining improvement:

- Replace E2B simulation with real Raspberry Pi 4/5 benchmark if hardware is available.

## 3. Functional Completeness - 20%

Evidence in project:

- Runnable web demo.
- Child-facing companion state.
- Seven-day aggregate family climate forecast.
- Parent default view hides exact events, counts, child behavior, and evidence IDs.
- Explicit guardian safety alert and authorized professional-support handoff preview.
- Text input and scenario buttons.
- Signal sliders.
- P0 safety escalation.
- Guardian consent dialog.
- Fallback behavior when the cloud climate outlook is slow or fails.

Demo proof:

- Normal, hidden distress, anger, and high-risk scenes are supported.
- Realtime edge response and deterministic safety continue while the climate outlook runs in background.

Remaining improvement:

- Deploy hosted demo URL.
- Add automated browser smoke test if time allows.

## 4. Innovation - 15%

Evidence in project:

- Embodied AI companion rather than chatbot-only UI.
- Edge realtime response separated from slower longitudinal Family Climate Outlook.
- Language/acoustic self-correction.
- Safety audit plus model reasoning instead of full model delegation.
- Parent guidance avoids interrogation and supports co-regulation.

Demo proof:

- Text-only rules vs multichannel edge reasoning panel.
- Family climate forecast and visible privacy boundary.
- Safety route keeps child companion gentle while parent sees escalation.

Positioning note:

- The submission should be described as a privacy-first edge emotional support system, not as an AI emotion toy.

Remaining improvement:

- Add small visual diagram or screenshot to the technical report after final deployment.

## 5. Presentation Quality - 10%

Evidence in project:

- README explains architecture, setup, privacy, and Gemma usage.
- Technical report is organized by judging dimensions.
- Deployment guide documents environment variables and provider options.
- Submission checklist tracks final deliverables.

Remaining improvement:

- Record final under-5-minute demo video.
- Add deployed URL to README after hosting.
