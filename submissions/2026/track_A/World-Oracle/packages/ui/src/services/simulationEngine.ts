import type { AgentState, WorldEvent } from "@world-oracle/shared";
import { AGENT_DOSSIERS } from "../data/agentDossiers";
import { REPLAY_FIXTURE } from "../data/replayFixture";
import { queryAgent, type GemmaToolTrace } from "./gemma";

const REPLAY_MODE = import.meta.env.VITE_REPLAY_MODE === "true";
const MAX_LIVE_GEMMA_AGENTS = Number(import.meta.env.VITE_MAX_LIVE_GEMMA_AGENTS || 1);

export interface AgentTurnResult {
  agentId: string;
  reasoning: string;
  memory: string;
  toolTrace: GemmaToolTrace[];
  action: {
    type: string;
    target: string | null;
    description: string;
    intensity: number;
  };
}

/**
 * Build the LLM system prompt for an agent.
 * Dossier (WHO they are) + injected current resource/relationship state.
 */
function buildSystemPrompt(agent: AgentState, dossier: string): string {
  const rels = Object.values(agent.relationships)
    .map((r) => `  ${r.targetAgentId}: alignment ${r.alignment > 0 ? "+" : ""}${r.alignment}`)
    .join("\n");

  return `${dossier}

CURRENT STATE:
Resources — Military: ${agent.resources.military}/100, Economic: ${agent.resources.economic}/100, Political: ${agent.resources.political}/100, Intelligence: ${agent.resources.intelligence}/100
Morale: ${agent.morale}/100 | Stability: ${agent.stability}/100
Relationships:
${rels}

GEMMA 4 AGENT CONTRACT:
Use function calling when the runtime supports it. Prefer propose_agent_action with this payload:
{
  "reasoning": "your internal analysis in 2-3 sentences",
  "action": {
    "type": "military|diplomatic|economic|intelligence|propaganda",
    "target": "agent_id (usa/iran/israel/russia/china/saudi/houthis/hezbollah) or null",
    "description": "what you are doing in one concrete sentence",
    "intensity": 0.1
  },
  "memory": "one durable lesson or observation to retain for the next turn"
}
intensity is 0.0 (minimal) to 1.0 (maximum escalation).`;
}

/**
 * Build the world state user prompt.
 * Includes both last turn's actions AND actions already taken this turn (by earlier agents).
 */
function buildWorldStatePrompt(
  agent: AgentState,
  allAgents: AgentState[],
  recentEvents: WorldEvent[],
  lastTurnActions: AgentTurnResult[],
  currentTurnActions: AgentTurnResult[], // agents who already moved this turn
  turn: number,
  globalTension: number,
): string {
  const agentName = (id: string) => allAgents.find((a) => a.id === id)?.persona.name || id;

  const eventLines = recentEvents
    .slice(-4)
    .map((e) => `  [T${e.turn}] ${e.agentId ? `[${e.agentId.toUpperCase()}] ` : ""}${e.description}`)
    .join("\n");

  const lastTurnLines =
    lastTurnActions.filter((a) => a.agentId !== agent.id).length > 0
      ? lastTurnActions
          .filter((a) => a.agentId !== agent.id)
          .map((a) => `  ${agentName(a.agentId)}: ${a.action.description} (${a.action.type}, intensity: ${a.action.intensity.toFixed(1)})`)
          .join("\n")
      : "  (No data)";

  const currentTurnLines =
    currentTurnActions.filter((a) => a.agentId !== agent.id).length > 0
      ? currentTurnActions
          .filter((a) => a.agentId !== agent.id)
          .map((a) => `  ${agentName(a.agentId)}: ${a.action.description} (${a.action.type}, intensity: ${a.action.intensity.toFixed(1)})`)
          .join("\n")
      : "  (You are moving first this turn)";

  return `SITUATION BRIEF — Turn ${turn} | Global Tension: ${globalTension}/100

RECENT INTELLIGENCE:
${eventLines || "  (No recent events)"}

LAST TURN — OTHER ACTORS:
${lastTurnLines}

THIS TURN — ACTIONS SO FAR (react to these):
${currentTurnLines}

What is your next strategic action? Respond with JSON only.`;
}

/**
 * Run one simulation turn sequentially — each agent sees actions already taken
 * this turn by earlier agents, enabling real inter-agent reaction.
 * onAgentAction is called immediately after each agent decides, for live UI updates.
 */
export async function runSimulationTurn(
  agents: AgentState[],
  worldEvents: WorldEvent[],
  lastTurnActions: AgentTurnResult[],
  turn: number,
  globalTension: number,
  onAgentAction?: (result: AgentTurnResult) => void,
): Promise<AgentTurnResult[]> {
  // Replay mode: stream fixture results with delays instead of calling API
  if (REPLAY_MODE) {
    const results: AgentTurnResult[] = [];
    for (const entry of REPLAY_FIXTURE) {
      const result: AgentTurnResult = {
        ...entry,
        memory: `Replay memory: ${entry.action.description}`,
        toolTrace: [
          {
            id: `${entry.agentId}-replay-context-${turn}`,
            name: "retrieve_agent_memory",
            status: "context",
            args: { agentId: entry.agentId, turn },
            result: "Replay mode uses pre-recorded Gemma-style agent context.",
          },
          {
            id: `${entry.agentId}-replay-action-${turn}`,
            name: "propose_agent_action",
            status: "parsed_content",
            args: entry.action,
            result: "Replay action injected for deterministic demo playback.",
          },
        ],
      };
      await new Promise((r) => setTimeout(r, 600));
      onAgentAction?.(result);
      results.push(result);
    }
    return results;
  }

  const currentTurnActions: AgentTurnResult[] = [];

  for (const agent of agents) {
    const dossier = AGENT_DOSSIERS[agent.id];
    if (!dossier) continue;

    if (currentTurnActions.length >= MAX_LIVE_GEMMA_AGENTS) {
      const result = buildDeferredAgentResult(agent, turn);
      currentTurnActions.push(result);
      onAgentAction?.(result);
      continue;
    }

    try {
      const systemPrompt = buildSystemPrompt(agent, dossier);
      const userPrompt = buildWorldStatePrompt(
        agent,
        agents,
        worldEvents,
        lastTurnActions,
        currentTurnActions,
        turn,
        globalTension,
      );

      const decision = await queryAgent(agent, systemPrompt, userPrompt, turn);

      const result: AgentTurnResult = {
        agentId: agent.id,
        reasoning: decision.reasoning,
        memory: decision.memory,
        toolTrace: decision.toolTrace,
        action: {
          type: decision.action.type,
          target: decision.action.target,
          description: decision.action.description,
          intensity: Math.max(0, Math.min(1, decision.action.intensity)),
        },
      };

      currentTurnActions.push(result);
      onAgentAction?.(result);
    } catch (err) {
      console.error(`[engine] agent ${agent.id} failed:`, err);
    }
  }

  return currentTurnActions;
}

function buildDeferredAgentResult(agent: AgentState, turn: number): AgentTurnResult {
  return {
    agentId: agent.id,
    reasoning:
      "This actor is preserving its current posture while the local Gemma demo prioritizes low-latency live inference for the lead agents.",
    memory: "Observed this turn as a secondary actor; no high-intensity move was authorized.",
    toolTrace: [
      {
        id: `${agent.id}-scheduler-${turn}`,
        name: "simulation_batch_scheduler",
        status: "executed",
        args: { agentId: agent.id, turn, maxLiveGemmaAgents: MAX_LIVE_GEMMA_AGENTS },
        result: "Deferred direct Gemma call to keep the local demo responsive.",
      },
      {
        id: `${agent.id}-deferred-action-${turn}`,
        name: "propose_agent_action",
        status: "executed",
        args: { type: "diplomatic", target: null, intensity: 0.1 },
        result: "Maintained posture and monitored lead-agent decisions.",
      },
    ],
    action: {
      type: "diplomatic",
      target: null,
      description: "Maintain current posture and monitor lead-agent escalation signals.",
      intensity: 0.1,
    },
  };
}
