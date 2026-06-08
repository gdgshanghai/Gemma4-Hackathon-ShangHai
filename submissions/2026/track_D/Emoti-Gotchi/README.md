# Emoti-Gotchi 情绪守护宠

Gemma 4 Developer Competition 2026 submission for Track D: AI for Social Good.

## Online Demo

https://emoti-gotchi.vercel.app

Emoti-Gotchi is a privacy-first edge emotional support system for children aged 6-8. It uses an embodied child-facing companion and a parent-facing emotional-weather report to help families respond to difficult feelings without turning the child into a surveillance target.

## What It Solves

Young children often lack the vocabulary to say "I feel anxious" or "I need help." They may say "I am fine" while their voice, breathing, hesitation, or crying probability tells a different story. Parents also need simple, calm guidance rather than raw transcripts or clinical dashboards.

The product is shaped by an East Asian family context described in the project plan: many children are encouraged to be quiet, resilient, and academically compliant, while parents often respond to distress through correction, reasoning, or advice before emotional validation. In the early primary-school window, roughly ages 6-8, children are still more willing to speak to parents, but they may express distress through ordinary events such as darkness, broken toys, or school transitions. Emoti-Gotchi is designed to protect that communication window by offering a low-pressure companion for the child and a calmer response cue for the guardian.

The interaction design is evidence-informed, but not clinically validated. It draws on child emotion understanding, parent emotion socialization, and supportive response theory: the companion uses facial expression, low-stimulation presence, and co-regulation language to help the child express feelings; the guardian view provides "what to do" and "what to avoid" so adults are guided away from interrogation, denial, or immediate lecturing. The safety and privacy architecture is also aligned with UNICEF child AI guidance, WHO AI ethics principles, and the NIST AI Risk Management Framework. The current prototype has not yet run child testing, guardian interviews, or independent expert review, so it does not claim diagnosis, treatment, or proven mental-health improvement.

Emoti-Gotchi turns this into two connected outputs:

- an immediate, gentle companion response for the child
- an emotional-weather report that translates the current support need into one simple parent action
- a seven-day family-climate view that summarizes when the home environment may need lower stimulation or more predictable support

The goal is prevention and family communication support. Emoti-Gotchi is not a diagnosis or treatment system.

### Why Emotional Weather

Emotional weather is a privacy and communication design, not a diagnosis or a label attached to
the child. Instead of showing a transcript, a behavior log, or a clinical score, it translates the
current support need into an intuitive parent-facing signal:

- `Sunny`: the child appears open; share the moment without taking over
- `Breezy`: keep stimulation low and allow quiet presence
- `Rainy`: offer gentle support without forcing an explanation
- `Storm Alert`: leave the metaphor and open an explicit guardian safety path

This lowers the guardian's cognitive load, reduces the impulse to interrogate or label the child,
and converts recognition into an immediate environment adjustment.

The seven-day **family climate** is the longer-term view of these privacy-minimized weather
signals. It describes recurring time and environment conditions where calmer lighting, quieter
transitions, or predictable presence may help. It does not report what the child said or judge the
child's personality.

## Competition Positioning

- Primary track: Track D, AI for Social Good
- Secondary strengths: multimodal reasoning and edge AI
- Core model: Gemma 4
- Current live cloud model: `gemma-4-26b-a4b-it`
- Edge target: Gemma 4 E2B-style local inference on Raspberry Pi 4/5, mobile device, or base station

## Product Architecture

The product intentionally separates real-time child response from slower parent review:

```text
Child utterance and local acoustic features
  |
  |-- Realtime edge path
  |     Gemma 4 E2B-style structured reasoning
  |     deterministic safety audit
  |     embodied expression, light, and sound
  |
  +-- Background family insight path
        de-identified structured events only
        Gemma 4 Family Climate Outlook
        trends, one gentle action, and uncertainty
```

This split exists because child-facing comfort must be low latency. Cloud Gemma 4 is valuable, but it is not used as the only real-time response path.

## Gemma 4 Usage

Emoti-Gotchi uses Gemma 4 as a structured emotional reasoning adapter, not as a generic chatbot. The child-facing demo uses an E2B-style edge simulation. Cloud Gemma 4 only receives de-identified structured family events; it never receives raw audio or controls the immediate child response.

The model task is:

1. compare child language with acoustic features
2. correct hidden distress when words and voice disagree
3. return a constrained JSON action
4. keep parent guidance calm, practical, and non-diagnostic

Example output:

```json
{
  "emotion_detected": "anxious",
  "anxiety_score": 8,
  "spoken_response": "You do not have to be brave alone. I can stay warm beside you.",
  "hardware_light_mode": "warm_orange",
  "hardware_sound_trigger": "soft_heartbeat",
  "capsule_state": "sad",
  "weather": "rainy",
  "guardian_headline": "Distress is present even though the words look calm",
  "guardian_action": "Give a quiet 10-second hug tonight and use a soft voice.",
  "guardian_avoid": "Avoid asking about school or forcing a reason right away."
}
```

## Product Loops

The web demo exposes two deliberately separated loops:

- `Realtime child support: On-device`: fast E2B-style edge simulation, constrained interaction strategy, and deterministic safety audit
- `Long-term family climate: Cloud Gemma 4`: real Gemma 4 call that identifies recurring time and environment conditions from de-identified history, then suggests one low-pressure environment adjustment

The comparison panel shows where text-only rules miss conflicting acoustic evidence. The family loop lets a guardian record an action and later state, then describes which actions are more often associated with improvement without claiming causation.

The interface is organized as a judging story:

- `Live Demo`: immediate child response, live structured signals, parent guidance, and safety state
- `Technical Proof`: Rules vs Gemma 4 E2B vs an on-demand real Cloud benchmark, plus the independent safety audit
- `Family Climate`: aggregate outlook that hides exact events, counts, and child behavior from the default parent view

## Safety and Privacy

- Raw audio is intended to stay on the local device.
- Cloud requests contain structured de-identified events, not raw audio, full child dialogue, or identity data.
- Parents receive summaries and one low-pressure action, not raw transcripts.
- Safety escalation is deterministic and independent from model output.
- High-risk language and extreme distress trigger a P0 guardian consent path.
- High-risk signals first open an explicit guardian alert with immediate safety steps.
- After explicit guardian consent, the product can offer a referral path to a vetted child-psychology professional or an appropriate local emergency resource.
- High-risk signals stop using the weather metaphor and become an explicit guardian safety alert.
- The current professional-support handoff is an authorization and referral-flow demo; it does not contact a real clinician.
- The product does not diagnose, treat, or replace professional care.

## Evidence-Informed Design References

- UNICEF, `Policy Guidance on AI for Children`: child wellbeing, privacy, safety, transparency, explainability, and accountability.
- WHO, `Ethics and governance of artificial intelligence for health`: human autonomy, transparency, responsibility, safety, and privacy boundaries for health-adjacent AI.
- NIST, `AI Risk Management Framework 1.0`: govern, map, measure, and manage AI risk instead of relying on model output alone.
- Parent emotion socialization intervention literature, including systematic review evidence, supports the product direction of helping guardians respond constructively rather than turning the AI into a child-facing therapist.

## Key Files

- UI dashboard: `src/components/emoti-gotchi/EmotiGotchiDashboard.tsx`
- Core graph and safety logic: `src/lib/emoti-gotchi-core.ts`
- Server-side Gemma adapter: `src/lib/api/gemma.functions.ts`
- Safe Google model HTTP helper: `src/lib/gemma-cloud.server.ts`
- Edge feasibility simulator: `tools/edge-feasibility-sim.mjs`
- Gemma cloud connectivity test: `tools/test-gemma-cloud.mjs`
- Technical report: `docs/TECHNICAL_REPORT.md`
- Scoring alignment: `docs/JUDGING_ALIGNMENT.md`
- Deployment guide: `docs/DEPLOYMENT.md`

## Local Setup

```bash
bun install
bun run dev
```

Create `.env.local`:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemma-4-26b-a4b-it
ALL_PROXY=socks5://127.0.0.1:1080
```

`ALL_PROXY` is only needed when the local terminal cannot directly access Google APIs.

Test Gemma connectivity:

```bash
bun run gemma:test
```

Run edge feasibility simulation:

```bash
bun run edge:sim
```

Build:

```bash
bun run build
```

## Submission Status

Completed:

- high-fidelity runnable demo
- real Gemma 4 Family Climate adapter over de-identified history
- seven-day aggregate family climate forecast and environment adjustment
- text-only rules versus multichannel edge reasoning comparison
- server-side API key protection
- E2B edge simulation and latency telemetry
- deterministic P0 safety audit
- guardian consent flow
- judging-aligned technical report
- production deployment: https://emoti-gotchi.vercel.app

Remaining external actions:

- record the final under-5-minute demo video
