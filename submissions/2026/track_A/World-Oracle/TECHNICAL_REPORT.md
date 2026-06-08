# World Oracle Gemma 4 Hackathon Technical Report

## Project Summary

World Oracle is a multi-agent geopolitical simulation dashboard. It models each party in a crisis as an autonomous strategic agent, then uses Gemma 4 to generate structured actions, durable memories, and outcome changes turn by turn.

The current demo uses a US-Iran conflict escalation scenario with eight actors: United States, Iran, Israel, Russia, China, Saudi Arabia, Houthis, and Hezbollah.

## Track Alignment

Primary track: **A - AI Agent**

World Oracle demonstrates:

- Multi-step planning through sequential turn orchestration.
- Agent-specific dossiers, objectives, resources, and relationship state.
- Durable memory written after each Gemma 4 decision.
- Tool-call traces displayed in the UI for reviewability.
- Dynamic world-state and prediction updates after each agent round.

Secondary framing: **D - Social Good**

The simulation is designed for crisis analysis and early warning. It highlights ceasefire likelihood, humanitarian corridor feasibility, regional war risk, and oil shock risk so analysts can compare de-escalation paths.

## Gemma 4 Model Choice

The demo targets `google/gemma-4-e4b` through a local OpenAI-compatible server at:

```text
http://127.0.0.1:1234/v1
```

Why this model is appropriate:

- It is lightweight enough for repeated local inference during a live multi-agent demo.
- It supports the same agent architecture that can scale to larger Gemma 4 variants.
- It keeps sensitive scenario prompts and local API credentials off cloud infrastructure.
- It is fast enough to run several actors sequentially while still producing useful strategic reasoning.

For a production or long-context research version, the same service interface can target `gemma-4-26B-A4B` for larger scenario context and deeper reasoning.

For the live hackathon demo, `VITE_MAX_LIVE_GEMMA_AGENTS=1` is used by default so slower local machines can complete a turn reliably. The remaining actors stay in the simulation and receive scheduler-deferred posture actions. Increasing this value runs more actors directly through Gemma 4.

The probability gauge uses a rotating local live-signal feed by default (`VITE_DISABLE_POLYMARKET=true`) so demos are not blocked by Polymarket CLOB connectivity. When network access is reliable, setting `VITE_DISABLE_POLYMARKET=false` switches the same gauge back to the real Polymarket midpoint.

## Architecture

```text
Dashboard
  |
  v
Simulation Store
  |
  v
Sequential Agent Turn Loop
  |
  v
Gemma 4 OpenAI-Compatible API Client
  |
  v
Tool Trace + Memory + Prediction Updates
```

Key files:

- `packages/ui/src/services/gemma.ts`
- `packages/ui/src/services/simulationEngine.ts`
- `packages/ui/src/stores/simulationStore.ts`
- `packages/ui/src/panels/ReasoningPanel.tsx`
- `packages/ui/src/panels/PredictionsPanel.tsx`

## Function Calling Design

The app sends Gemma 4 a function schema for `propose_agent_action`.

Expected action payload:

```json
{
  "reasoning": "two concise sentences",
  "type": "diplomatic",
  "target": "iran",
  "description": "Open a backchannel through a neutral mediator.",
  "intensity": 0.35,
  "memory": "Backchannel diplomacy is viable if oil-shock pressure rises."
}
```

The UI records each turn as:

1. `retrieve_agent_memory`
2. `propose_agent_action`
3. `write_agent_memory`

Local runtimes differ in how they expose tool calls. If the runtime returns OpenAI-style `tool_calls`, the app records the native tool call. If the runtime returns JSON content, the app normalizes it into the same trace shape so the simulation remains robust during a live demo.

## Multi-Agent Advantage

Gemma 4 is especially useful here because the simulation is not a single answer. The model is repeatedly asked to reason from different strategic perspectives:

- The United States weighs deterrence, oil transit, and alliance credibility.
- Iran weighs regime survival, proxy escalation, and nuclear hedging.
- Israel weighs preemption, intelligence, and missile defense.
- China weighs mediation against energy security.
- Russia weighs indirect support against direct confrontation risk.

Each agent receives the same world state but different goals, constraints, and relationships. This makes Gemma 4's structured reasoning and tool-call discipline more valuable than a single prompt-based forecast.

## Data and Compliance

The current demo uses public scenario data and manually curated open-source intelligence summaries. It does not ingest private personal data. The local model workflow reduces data exposure because prompts stay on the machine running the demo.

## Known Limitations

- The current scenario fixture is static; the next version should support arbitrary event input and party extraction.
- Local OpenAI-compatible Gemma runtimes vary in native tool-call formatting, so the app includes schema normalization fallback.
- Predictions are heuristic functions of Gemma-selected actions and should be treated as decision support, not factual forecasts.

## Future Work

- Add multimodal intake for map screenshots and news images.
- Add event input and Gemma-powered party extraction.
- Add richer external tools for public data retrieval, sanctions lookup, and shipping/oil indicators.
- Run larger Gemma 4 variants for long-context scenario replay.
