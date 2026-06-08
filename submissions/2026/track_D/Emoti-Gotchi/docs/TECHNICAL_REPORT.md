# Emoti-Gotchi Technical Report

## Executive Summary

Emoti-Gotchi is a Gemma 4 powered privacy-first edge emotional support system for children. It targets a common family communication gap: a young child may say "I am fine" while acoustic signals suggest fear, sadness, or hidden distress. Parents need a calm bridge into better interaction, not surveillance or a raw data dashboard.

The demo implements a privacy-first architecture:

- realtime child-facing response through a Gemma 4 E2B-style edge path
- asynchronous Gemma 4 Family Climate Outlook that identifies recurring time and environment conditions from de-identified structured history
- deterministic safety audit independent from model output
- constrained hardware JSON for embodied expression, light, sound, and parent guidance

Current live cloud model: `gemma-4-26b-a4b-it`.

## 1. Real-World Impact - 30%

### Problem

Children aged 6-8 often do not yet have mature emotional vocabulary. This makes the early primary-school period an important opportunity to build habits of emotional expression and calm parent response. Emoti-Gotchi treats this as an early communication-support opportunity, not a claim that later support is ineffective or that every crisis can be prevented.

The project plan frames this need in an East Asian family context. Children may be socialized to be quiet, resilient, and academically compliant, while guardians under pressure may move quickly into correction, explanation, or advice. This can turn ordinary moments such as bedtime darkness, a broken toy, or a school transition into missed emotional signals. The product therefore focuses on the early primary-school window: when children are still relatively open to family support, Emoti-Gotchi tries to make emotional expression easier and guardian responses less interrogative.

This is a prevention-oriented communication design, not a clinical claim. The prototype uses synthetic scenarios and desktop validation only.

### Target Users

- children aged 6-8
- parents and guardians
- future school or family-support pilots

### Product Outcome

Emoti-Gotchi is designed to improve family communication before a crisis forms. It does not diagnose or treat. It helps with:

- noticing hidden distress earlier
- giving parents a simple next action
- preserving the child's feeling of safety
- alerting the guardian when a high-risk signal is detected, then offering a professional-support referral path only after explicit guardian consent

### Prevention Rationale and Product Boundaries

The product focuses on the early primary-school years because children at this stage may express
distress through ordinary situations rather than mature psychological language, while family
response habits are still being formed. The intended intervention is modest: help a child practice
expression and help a guardian practice calm, non-interrogative responses.

The product deliberately rejects comprehensive monitoring:

- current support needs are translated into an emotional-weather report so guardians receive one understandable response cue instead of a transcript, behavior log, or clinical score
- multiple days of privacy-minimized weather signals become a family-climate view that describes recurring time and environment conditions, not the child's personality
- the parent view hides exact events, exact counts, raw audio, full dialogue, and identity fields
- the system provides one low-pressure environment adjustment rather than a clinical conclusion
- high-risk signals are the explicit exception: a deterministic local audit leaves the weather metaphor and alerts the guardian directly
- the alert first provides immediate guardian actions; professional consultation requires guardian authorization and a vetted child-psychology provider or appropriate local emergency resource

The prototype does not claim that every crisis can be prevented, that later support is ineffective,
or that the product has been clinically validated.

### Evidence-Informed Design Basis

Emoti-Gotchi uses evidence-informed design and authoritative safety frameworks in place of real child testing at the competition prototype stage:

- Child emotion understanding: the child-facing companion uses simple emotional expressions, low-pressure language, and co-regulation cues because young children may not yet have mature emotion vocabulary.
- Parent emotion socialization: the guardian interface gives one concrete action and one avoid item, encouraging supportive responses instead of punishment, denial, interrogation, or immediate lecturing.
- UNICEF `Policy Guidance on AI for Children`: the architecture prioritizes child wellbeing, privacy, safety, transparency, and accountability.
- WHO `Ethics and governance of artificial intelligence for health`: the product keeps human autonomy, privacy, transparency, and responsibility boundaries explicit.
- NIST `AI Risk Management Framework 1.0`: the deterministic safety audit and risk boundary separate model reasoning from safety decisions.

The current prototype has not conducted child testing, guardian interviews, clinical validation, or independent expert review. Any real pilot should begin with guardian consent, child assent where applicable, child-safety expert review, minimal data retention, and a vetted escalation policy.

### Scalability

The system is designed as a two-layer deployment:

- local edge layer for privacy-preserving realtime response
- cloud insight layer for slower parent trends, one-action guidance, and uncertainty

This allows pilots to begin with a web demo, then migrate to Raspberry Pi, mobile, or base-station edge prototypes without changing the core action schema.

## 2. Technical Excellence - 25%

### 2.1 Architecture

```text
Child speech and acoustic signals
  |
  |-- ASR semantic channel
  |-- acoustic feature channel
  |      voice stress, crying probability, throat tremor, breathing pattern
  |
  +-- Realtime edge path
  |     Gemma 4 E2B-style constrained reasoning
  |     deterministic safety audit
  |     hardware action JSON
  |
  +-- Background family insight path
        de-identified structured events only
        Gemma 4 Family Climate Outlook
        trend, evidence IDs, one action, and uncertainty
```

The key technical decision is the product split:

- realtime child comfort must not wait for cloud latency
- cloud Gemma 4 is used for longitudinal parent insight only
- cloud output cannot override the edge safety audit or child response

### 2.2 Gemma 4 Usage

Gemma 4 is used for structured longitudinal reasoning. The cloud model is asked to compare de-identified events, cite event IDs, state uncertainty, and return one gentle action. It is not asked to chat with the child.

Current cloud call:

- model: `gemma-4-26b-a4b-it`
- adapter: server-side Google Generative Language API request
- key storage: `.env.local` / deployment environment variables only
- output validation: Zod schema + evidence ID filtering
- input boundary: no raw audio, full child dialogue, or identity fields

Edge path:

- current status: E2B edge simulation
- target: quantized Gemma 4 E2B-style runtime on Raspberry Pi 4/5, mobile, or base station
- telemetry: TTFT, total latency, memory estimate, schema validity, confidence

### 2.3 Constrained Action Schema

```json
{
  "emotion_detected": "anxious",
  "anxiety_score": 8,
  "spoken_response": "You do not have to be brave alone.",
  "hardware_light_mode": "warm_orange",
  "hardware_sound_trigger": "soft_heartbeat",
  "capsule_state": "sad",
  "weather": "rainy",
  "guardian_headline": "Distress is present even though the words look calm",
  "guardian_action": "Give a quiet 10-second hug tonight and use a soft voice.",
  "guardian_avoid": "Avoid asking about school or forcing a reason right away.",
  "signal_summary": "Acoustic distress is high despite calm words.",
  "rationale": "Speech and acoustic channels disagree."
}
```

This schema supports embodied edge behavior, parent guidance, audit trace, and later hardware control.

### 2.4 Safety Design

The P0 safety audit is deterministic and independent from Gemma 4. It checks:

- high-risk language
- extreme acoustic evidence
- high model anxiety score combined with acoustic risk

This protects against model delay, uncertainty, or hallucination. The product first alerts the
guardian and provides immediate safety steps. It may then offer a referral path to a vetted
child-psychology professional, but only after explicit guardian consent. The current prototype
demonstrates this authorization and referral flow; it does not contact a real clinician or replace
emergency services.

### 2.5 State Versioning

The demo exposes `state_version` and event logs. This reflects the planned edge/cloud synchronization model where local interaction can continue while cloud review arrives later.

## 3. Functional Completeness - 20%

The runnable demo includes:

- child room / local edge panel
- adjustable voice stress, acoustic stress, and crying probability
- embodied companion state with four core expressions
- emotional-weather report that translates current support needs into one parent action
- seven-day family-climate outlook that summarizes recurring time and environment conditions without exposing transcripts or child behavior logs
- environment-level settling index and broad time windows
- exact events, counts, and child behavior hidden from the default parent view
- deterministic P0 escalation
- guardian consent dialog
- Gemma 4 hardware JSON display
- trace panel with model/runtime/schema telemetry
- deployment mode switch
- text-only rules vs multichannel edge reasoning comparison
- privacy-minimized family climate forecast
- explicit safety exception and guardian-authorized professional handoff preview

Demo paths:

- regulated sharing
- hidden distress self-correction
- anger/frustration without crisis escalation
- high-risk language and guardian escalation

Failure handling:

- if cloud Gemma is slow or fails, edge interaction and safety remain active
- if history is insufficient, the climate outlook returns `insufficient_data`
- API key remains server-side
- local proxy support is documented for development environments

## 4. Innovation - 15%

The project is not a generic chatbot or a simple emotion classifier. Its novelty is the combined system:

- embodied AI companion as emotional container
- dual-channel self-correction between language and voice evidence
- child-facing response separated from parent-facing review
- deterministic safety audit combined with Gemma reasoning
- structured hardware JSON for lights, sound, expression, and parent guidance
- edge-first privacy with cloud Family Climate Outlook as background longitudinal analysis

This creates a product story where Gemma 4 is not just generating text; it is coordinating an embodied family-support workflow.

## 5. Presentation Quality - 10%

The demo is designed for a five-minute judging flow:

1. State the problem: young children hide distress behind ordinary words.
2. Show realtime E2B edge response for a normal utterance.
3. Show "I am fine" hidden distress correction.
4. Show rules baseline vs Gemma reasoning.
5. Show P0 safety escalation and guardian consent.
6. Show Gemma 4 Family Climate Outlook hiding event-level behavior while retaining uncertainty.
7. Close with privacy, prevention, and edge deployment roadmap.

Supporting artifacts:

- `README.md`
- `docs/JUDGING_ALIGNMENT.md`
- `docs/EDGE_FEASIBILITY.md`
- `docs/DEPLOYMENT.md`
- `docs/SUBMISSION_CHECKLIST.md`

## 6. Current Implementation Status

Completed:

- runnable UI demo
- real Gemma 4 cloud connectivity through `gemma-4-26b-a4b-it`
- safe server-side API key handling
- proxy-supported local development
- E2B edge simulation
- P0 safety audit
- structured schema validation
- parent consent flow
- complete guardian observation-action-follow-up loop
- de-identified seven-day Family Climate input boundary
- judging-aligned documentation

Not claimed:

- real Raspberry Pi Gemma 4 E2B benchmark
- medical diagnosis
- production child-safety certification

## 7. Edge Validation Plan

The next hardware validation step is to test the E2B edge path on:

- Raspberry Pi 4 8GB as stress target
- Raspberry Pi 5 8GB as preferred MVP target
- mobile phone or base station as fallback compute

Acceptance targets:

- deterministic safety audit under 50 ms
- feature extraction under 200 ms
- E2B TTFT under 2000 ms
- end-to-end hidden distress response under 2500 ms
- peak memory under 5.5 GB
- hidden-distress recall above 85% on a consent-safe validation set
- safety recall above 95% on red-flag scenarios

## 8. Responsible AI Statement

Emoti-Gotchi is a family communication aid and risk sentinel. It does not diagnose, treat, or replace professional care. Normal support uses a privacy-preserving household climate metaphor; high-risk signals bypass that metaphor and trigger an explicit guardian alert. The current handoff is a consent demonstration and does not connect to a real clinician. Any real pilot must use consented data, expert review, vetted professional partners, guardian controls, and a clear escalation policy.

The evidence basis is used to justify design constraints, not to claim efficacy. The submission should be read as a safety-conscious prototype that combines Gemma 4 reasoning with deterministic guardrails, privacy minimization, and human authorization.
