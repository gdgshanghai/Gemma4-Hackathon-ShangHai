import type { ActionType, AgentState, WorldEvent } from "@world-oracle/shared";

const GEMMA_PROXY = "/api/gemma";
export const GEMMA_MODEL = import.meta.env.VITE_MODEL_NAME || "google/gemma-4-e4b";
const GEMMA_TIMEOUT_MS = Number(import.meta.env.VITE_GEMMA_TIMEOUT_MS || 30_000);

const ACTION_TYPES: ActionType[] = [
	"military",
	"diplomatic",
	"economic",
	"intelligence",
	"propaganda",
	"humanitarian",
];

export interface GemmaToolTrace {
	id: string;
	name: string;
	status: "context" | "model_tool_call" | "parsed_content" | "executed";
	args: Record<string, unknown>;
	result: string;
}

export interface AgentDecision {
	reasoning: string;
	memory: string;
	toolTrace: GemmaToolTrace[];
	action: {
		type: ActionType;
		target: string | null;
		description: string;
		intensity: number;
	};
}

interface ChatMessage {
	role: "system" | "user" | "assistant" | "tool";
	content: string;
	tool_call_id?: string;
}

interface ToolCall {
	id?: string;
	function?: {
		name?: string;
		arguments?: string;
	};
}

const FALLBACK_DECISION: AgentDecision = {
	reasoning: "Maintaining current posture while validating local Gemma 4 output.",
	memory: "Local runtime returned no schema-complete tool call, so a low-risk diplomatic posture was preserved.",
	toolTrace: [],
	action: {
		type: "diplomatic",
		target: null,
		description: "Hold position and monitor developments.",
		intensity: 0.1,
	},
};

const GEMMA_AGENT_TOOLS = [
	{
		type: "function",
		function: {
			name: "propose_agent_action",
			description:
				"Choose the next strategic action for one geopolitical simulation agent.",
			parameters: {
				type: "object",
				properties: {
					reasoning: {
						type: "string",
						description: "Two concise sentences explaining the decision.",
					},
					type: {
						type: "string",
						enum: ACTION_TYPES,
						description: "Action category.",
					},
					target: {
						type: "string",
						description: "Target agent id, or null/none if no target.",
					},
					description: {
						type: "string",
						description: "One concrete action sentence.",
					},
					intensity: {
						type: "number",
						description: "Escalation level from 0.0 to 1.0.",
					},
					memory: {
						type: "string",
						description: "A durable memory item this agent should retain.",
					},
				},
				required: ["reasoning", "type", "description", "intensity", "memory"],
			},
		},
	},
	{
		type: "function",
		function: {
			name: "update_outcome_prediction",
			description:
				"Estimate how this action changes ceasefire, escalation, humanitarian, and market risks.",
			parameters: {
				type: "object",
				properties: {
					ceasefire: { type: "number" },
					regionalWar: { type: "number" },
					humanitarianRisk: { type: "number" },
					oilShock: { type: "number" },
				},
				required: ["ceasefire", "regionalWar", "humanitarianRisk", "oilShock"],
			},
		},
	},
];

function clamp01(value: unknown, fallback: number) {
	const n = typeof value === "number" ? value : Number.parseFloat(String(value));
	return Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : fallback;
}

function normalizeActionType(value: unknown): ActionType {
	const normalized = String(value ?? "").toLowerCase();
	return ACTION_TYPES.includes(normalized as ActionType)
		? (normalized as ActionType)
		: "diplomatic";
}

function normalizeTarget(value: unknown): string | null {
	if (value === null || value === undefined) return null;
	const normalized = String(value).trim();
	if (!normalized || ["null", "none", "n/a", "no target"].includes(normalized.toLowerCase())) {
		return null;
	}
	return normalized;
}

function extractJsonObject(text: string): unknown {
	const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
	const candidate = fenced?.[1] ?? text.match(/\{[\s\S]*\}/)?.[0] ?? text;
	return JSON.parse(candidate);
}

function parseToolArgs(args: string | undefined): Record<string, unknown> {
	if (!args) return {};
	try {
		return extractJsonObject(args) as Record<string, unknown>;
	} catch {
		return {};
	}
}

function decisionFromObject(value: Record<string, unknown>): AgentDecision {
	const action = (value.action ?? value) as Record<string, unknown>;
	const description =
		action.description ?? action.details ?? value.description ?? "Maintain posture and monitor developments.";

	return {
		reasoning: String(value.reasoning ?? action.reasoning ?? "Gemma 4 selected a conservative next action."),
		memory: String(
			value.memory ??
				action.memory ??
				`Action selected: ${String(description).slice(0, 120)}`,
		),
		toolTrace: [],
		action: {
			type: normalizeActionType(action.type ?? value.type),
			target: normalizeTarget(action.target ?? value.target),
			description: String(description),
			intensity: clamp01(action.intensity ?? value.intensity, 0.1),
		},
	};
}

async function postChat(body: Record<string, unknown>) {
	const controller = new AbortController();
	const timeout = window.setTimeout(() => controller.abort(), GEMMA_TIMEOUT_MS);
	const res = await fetch(`${GEMMA_PROXY}/v1/chat/completions`, {
		method: "POST",
		headers: { "content-type": "application/json" },
		body: JSON.stringify(body),
		signal: controller.signal,
	}).finally(() => window.clearTimeout(timeout));

	if (!res.ok) {
		const text = await res.text();
		throw new Error(`Gemma API error ${res.status}: ${text}`);
	}

	return res.json();
}

async function postChatWithToolFallback(body: Record<string, unknown>) {
	try {
		const data = await postChat(body);
		const message = data.choices?.[0]?.message;
		const content = String(message?.content ?? "").trim();
		const toolCalls = message?.tool_calls ?? [];
		if ("tools" in body && toolCalls.length === 0 && !content) {
			const { tools: _tools, tool_choice: _toolChoice, ...retryBody } = body;
			return postChat(retryBody);
		}
		return data;
	} catch (err) {
		if (!("tools" in body)) throw err;
		const { tools: _tools, tool_choice: _toolChoice, ...retryBody } = body;
		return postChat(retryBody);
	}
}

function buildContextTrace(agent: AgentState, turn: number): GemmaToolTrace {
	const recentMemory = agent.memory.slice(-4).map((m) => `[T${m.turn}] ${m.content}`);
	return {
		id: `${agent.id}-memory-${turn}`,
		name: "retrieve_agent_memory",
		status: "context",
		args: { agentId: agent.id, turn },
		result: recentMemory.length > 0 ? recentMemory.join(" | ") : "No prior durable memories.",
	};
}

function decisionFromToolCall(call: ToolCall): AgentDecision | null {
	const name = call.function?.name;
	if (name !== "propose_agent_action") return null;
	const args = parseToolArgs(call.function?.arguments);
	const decision = decisionFromObject(args);
	decision.toolTrace.push({
		id: call.id ?? `tool-${Date.now()}`,
		name,
		status: "model_tool_call",
		args,
		result: `${decision.action.type} action accepted at intensity ${decision.action.intensity.toFixed(2)}`,
	});
	return decision;
}

function appendMemoryTrace(decision: AgentDecision, agentId: string, turn: number) {
	decision.toolTrace.push({
		id: `${agentId}-write-memory-${turn}`,
		name: "write_agent_memory",
		status: "executed",
		args: { agentId, turn, type: "reflection" },
		result: decision.memory,
	});
}

export async function queryWarEndsProbability(
	agents: AgentState[],
	worldEvents: WorldEvent[],
	globalTension: number,
	turn: number,
): Promise<number> {
	const agentSummary = agents
		.map((a) => `${a.persona.name}: mil=${a.resources.military} eco=${a.resources.economic} morale=${a.morale} stability=${a.stability}`)
		.join("\n");

	const recentEvents = worldEvents
		.slice(-6)
		.map((e) => `[T${e.turn}][${e.severity}] ${e.description}`)
		.join("\n");

	const prompt = `You are Gemma 4 running a multi-agent geopolitical simulation calibration step.

Estimate the probability that the Iran-Israel-US conflict ends by December 31, 2026.

CURRENT SIMULATION STATE (Turn ${turn})
Global Tension: ${globalTension}/100

ACTOR STATUS:
${agentSummary}

RECENT EVENTS:
${recentEvents}

Respond with JSON only: {"probability": 0.XX, "rationale": "one sentence"}`;

	const data = await postChat({
		model: GEMMA_MODEL,
		temperature: 0.1,
		max_tokens: 120,
		messages: [{ role: "user", content: prompt }],
	});

	const text: string = data.choices?.[0]?.message?.content ?? "";
	try {
		const parsed = extractJsonObject(text) as { probability?: unknown };
		return clamp01(parsed.probability, 0.5);
	} catch {
		return 0.5;
	}
}

export async function queryAgent(
	agent: AgentState,
	systemPrompt: string,
	userPrompt: string,
	turn: number,
): Promise<AgentDecision> {
	const contextTrace = buildContextTrace(agent, turn);
	const messages: ChatMessage[] = [
		{ role: "system", content: systemPrompt },
		{
			role: "user",
			content: `${userPrompt}

Use Gemma 4's function calling when available. Prefer propose_agent_action. If the local runtime does not emit tool_calls, respond with a single JSON object matching:
{"reasoning":"two sentences","action":{"type":"military|diplomatic|economic|intelligence|propaganda|humanitarian","target":"agent id or null","description":"one concrete action sentence","intensity":0.1},"memory":"one durable memory"}`,
		},
	];

	const body = {
		model: GEMMA_MODEL,
		temperature: 0.25,
		max_tokens: 360,
		tools: GEMMA_AGENT_TOOLS,
		tool_choice: "auto",
		messages,
	};

	try {
		const data = await postChatWithToolFallback(body);
		const message = data.choices?.[0]?.message;
		const toolCalls: ToolCall[] = message?.tool_calls ?? [];
		const toolDecision = toolCalls.map(decisionFromToolCall).find(Boolean);

		if (toolDecision) {
			toolDecision.toolTrace.unshift(contextTrace);
			appendMemoryTrace(toolDecision, agent.id, turn);
			return toolDecision;
		}

		const text: string = message?.content ?? "";
		const parsed = extractJsonObject(text) as Record<string, unknown>;
		const decision = decisionFromObject(parsed);
		decision.toolTrace = [
			contextTrace,
			{
				id: `${agent.id}-parsed-action-${turn}`,
				name: "propose_agent_action",
				status: "parsed_content",
				args: parsed,
				result: `${decision.action.type} action normalized from Gemma JSON output.`,
			},
		];
		appendMemoryTrace(decision, agent.id, turn);
		return decision;
	} catch (err) {
		console.error(`[gemma:${agent.id}] turn ${turn} failed:`, err);
		return {
			...FALLBACK_DECISION,
			toolTrace: [
				contextTrace,
				{
					id: `${agent.id}-fallback-${turn}`,
					name: "propose_agent_action",
					status: "parsed_content",
					args: {},
					result: "Schema fallback selected after the local runtime returned no complete tool payload.",
				},
			],
		};
	}
}
