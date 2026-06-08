# Edge Feasibility Validation

## Goal

Validate whether the Emoti-Gotchi edge layer can meet the product goals:

- low latency
- high hidden-distress correction accuracy
- high safety recall
- local privacy
- stable hardware behavior

The target is not to prove a medical diagnosis system. The target is to prove that a Raspberry Pi 4 8GB-class prototype can run the product loop well enough for a competition demo and later pilot.

## Hardware targets

| Target | Role | Feasibility expectation |
| --- | --- | --- |
| Raspberry Pi 4 8GB | first feasibility target | Useful stress test; likely acceptable for structured, short-output E2B simulation if quantized |
| Raspberry Pi 5 8GB | preferred MVP prototype | Better first public demo target for local Gemma-style inference |
| Android phone / tablet | companion compute | Strong fallback for camera/audio extension and better acceleration |
| Toy MCU only | always-on controller | Good for lights, sound, buttons, and deterministic safety keywords; not enough for full LLM inference |
| Edge SoC with NPU | production direction | Best route for lower latency and power efficiency |

## Validation architecture

```text
Microphone input
  |
  |-- 50-200 ms acoustic windows
  |-- short ASR phrase transcript
  |
  v
Feature packet
  {
    spokenText,
    voiceStress,
    acousticStress,
    cryingProbability,
    speechRateDelta,
    throatTremor,
    breathingPattern
  }
  |
  v
Gemma 4 E2B-style edge model
  |
  v
Constrained JSON
  |
  v
Deterministic safety audit
  |
  v
Hardware action + parent summary
```

## Benchmark metrics

| Metric | Target | Why it matters |
| --- | --- | --- |
| Safety keyword audit latency | under 50 ms | P0 protection cannot wait for model output |
| Acoustic feature window | 50-200 ms | Hidden distress relies on voice evidence |
| E2B TTFT on Raspberry Pi 4 8GB | under 2000 ms | Child-facing interaction must feel responsive |
| End-to-end scenario latency | under 2500 ms | Demo must feel near real-time |
| Peak memory | under 5.5 GB | Leaves room for OS and audio pipeline |
| Hidden-distress recall | 85%+ on validation set | Core product value is catching masked distress |
| Safety recall | 95%+ on red-flag scenarios | False negatives are unacceptable |
| False positive handling | parent-safe guidance | False positives should not punish the child |

## Validation dataset

Start with a small, consent-safe test set:

- 30 normal sharing samples
- 30 masked-distress samples
- 20 anger/frustration samples
- 20 safety-red-flag samples

For the competition prototype, synthetic and acted samples are acceptable if clearly labeled. For any real pilot, use consented data and professional review.

## Experiment plan

1. Run the web demo logic with simulated signals.
2. Run `node tools/edge-feasibility-sim.mjs` to validate the hardware budget.
3. Replace simulated model latency with real E2B benchmark results.
4. Measure end-to-end latency on Raspberry Pi 4 8GB.
5. Tune threshold policy:
   - increase safety recall first
   - reduce false positives second
6. Document every tradeoff in the technical report.

## Product decision from edge validation

If Raspberry Pi 4 8GB meets the budget:

- proceed with local prototype
- add microphone capture and feature extraction
- connect real Gemma 4 E2B runtime

If Raspberry Pi 4 8GB misses the budget:

- keep deterministic safety and acoustic features on-device
- move Gemma 4 reasoning to Raspberry Pi 5, a phone, or a base station
- send only structured features, not raw audio

If toy-only MCU is required:

- run only deterministic safety phrases and simple acoustic thresholds locally
- use paired phone/base station for Gemma 4 reasoning

## Current conclusion

The most credible MVP path is a two-layer edge design:

- always-on local safety and acoustic layer
- Gemma 4 E2B-style inference on Raspberry Pi 4/5, mobile device, or base station

This still preserves the product promise: raw audio stays local, latency is low enough for interaction, and high-risk conditions get immediate handling.
