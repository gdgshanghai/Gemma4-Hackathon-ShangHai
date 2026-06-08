import type {
	AgentAction,
	AgentState,
	Conflict,
	GlobalEvent,
	SimulationResult,
	SimulationStatus,
	WorldEvent,
} from "@world-oracle/shared";
import { create } from "zustand";
import type { AgentTurnResult } from "../services/simulationEngine";
import { runSimulationTurn } from "../services/simulationEngine";
import { queryWarEndsProbability, type GemmaToolTrace } from "../services/gemma";
import { useAiProbabilityStore } from "./aiProbabilityStore";
import { usePolymarketStore } from "./polymarketStore";

export interface AgentReasoning {
	agentId: string;
	turn: number;
	thought: string;
	memory: string;
	toolTrace: GemmaToolTrace[];
}

export interface ActionToast {
	id: string;
	agentId: string;
	agentName: string;
	agentColor: string;
	turn: number;
	action: {
		type: string;
		target: string | null;
		description: string;
		intensity: number;
	};
}

export interface OutcomePrediction {
	outcome: string;
	probability: number;
	trend: "up" | "down" | "stable";
	rationale: string;
}

interface SimulationStore {
	status: SimulationStatus;
	turn: number;
	maxTurns: number;
	event: GlobalEvent | null;
	agents: AgentState[];
	conflicts: Conflict[];
	worldEvents: WorldEvent[];
	actions: AgentAction[];
	result: SimulationResult | null;
	globalTension: number;
	isPlaying: boolean;
	agentReasoning: AgentReasoning[];
	lastTurnActions: AgentTurnResult[];
	isRunningTurn: boolean;
	actionToasts: ActionToast[];
	outcomePredictions: OutcomePrediction[];

	setStatus: (status: SimulationStatus) => void;
	advanceTurn: () => void;
	togglePlay: () => void;
	loadMockScenario: () => void;
	runTurn: () => Promise<void>;
	dismissToast: (id: string) => void;
}

export const useSimulationStore = create<SimulationStore>((set, get) => ({
	status: "running",
	turn: 47,
	maxTurns: 120,
	event: null,
	agents: [],
	conflicts: [],
	worldEvents: [],
	actions: [],
	result: null,
	globalTension: 78,
	isPlaying: false,
	agentReasoning: [],
	lastTurnActions: [],
	isRunningTurn: false,
	actionToasts: [],
	outcomePredictions: initialOutcomePredictions(),

	setStatus: (status) => set({ status }),
	advanceTurn: () => set((s) => ({ turn: Math.min(s.turn + 1, s.maxTurns) })),
	togglePlay: () => set((s) => ({ isPlaying: !s.isPlaying })),
	dismissToast: (id) => set((s) => ({ actionToasts: s.actionToasts.filter((t) => t.id !== id) })),

	runTurn: async () => {
		const { agents, worldEvents, lastTurnActions, turn, globalTension, isRunningTurn } = get();

		if (agents.length === 0) return;
		if (isRunningTurn) return;

		set({ isRunningTurn: true, actionToasts: [] });

		try {
			const results = await runSimulationTurn(
				agents,
				worldEvents,
				lastTurnActions,
				turn,
				globalTension,
				(result) => {
					const agent = get().agents.find((a) => a.id === result.agentId);
					const toast: ActionToast = {
						id: `${result.agentId}-${Date.now()}`,
						agentId: result.agentId,
						agentName: agent?.persona.name ?? result.agentId,
						agentColor: agent?.color ?? "#666",
						turn: get().turn,
						action: result.action,
					};
					set((s) => ({ actionToasts: [...s.actionToasts, toast] }));
				},
			);

			const nextTurn = turn + 1;

			const newReasoning: AgentReasoning[] = results.map((r) => ({
				agentId: r.agentId,
				turn: nextTurn,
				thought: r.reasoning,
				memory: r.memory,
				toolTrace: r.toolTrace,
			}));

			const newEvents: WorldEvent[] = results.map((r) => {
				const agent = agents.find((a) => a.id === r.agentId);
				return {
					turn: nextTurn,
					timestamp: new Date(),
					type: r.action.type,
					description: `${agent?.persona.name ?? r.agentId}: ${r.action.description}`,
					agentId: r.agentId,
					severity: r.action.intensity >= 0.7 ? "high" : r.action.intensity >= 0.4 ? "medium" : "low",
				};
			});

			const newActions: AgentAction[] = results.map((r) => ({
				agentId: r.agentId,
				turn: nextTurn,
				type: r.action.type as AgentAction["type"],
				target: r.action.target ?? "",
				intensity: r.action.intensity,
				description: r.action.description,
				reasoning: r.reasoning,
			}));

			// Drift tension toward average action intensity
			const avgIntensity =
				results.reduce((acc, r) => acc + r.action.intensity, 0) / Math.max(results.length, 1);
			const newTension = Math.round(
				Math.min(100, Math.max(0, globalTension * 0.85 + avgIntensity * 100 * 0.15)),
			);
			const outcomePredictions = buildOutcomePredictions(results, newTension);

			set((s) => ({
				agents: s.agents.map((agent) => {
					const result = results.find((r) => r.agentId === agent.id);
					if (!result) return agent;
					return {
						...agent,
						memory: [
							...agent.memory,
							{
								turn: nextTurn,
								type: "reflection" as const,
								content: result.memory,
								importance: Math.max(1, Math.round(result.action.intensity * 10)),
							},
						].slice(-12),
					};
				}),
				agentReasoning: [...newReasoning, ...s.agentReasoning].slice(0, 24),
				worldEvents: [...s.worldEvents, ...newEvents],
				actions: [...s.actions, ...newActions],
				lastTurnActions: results,
				globalTension: newTension,
				outcomePredictions,
				turn: Math.min(nextTurn, s.maxTurns),
				isRunningTurn: false,
			}));

			// Re-evaluate Gemma war-ends probability with updated world state (fire-and-forget)
			const updatedState = get();
			queryWarEndsProbability(
				updatedState.agents,
				updatedState.worldEvents,
				updatedState.globalTension,
				nextTurn,
			).then((p) => {
				const mktProbability = usePolymarketStore.getState().probability;
				const capped =
					mktProbability !== null
						? Math.min(mktProbability + 0.1, Math.max(mktProbability - 0.1, p))
						: p;
				useAiProbabilityStore.getState().update(capped);
			}).catch(() => {});

		} catch (err) {
			console.error("runTurn failed:", err);
			set({ isRunningTurn: false });
		}
	},

	loadMockScenario: () => {
		const agents: AgentState[] = [
			{
				id: "usa",
				partyId: "usa",
				persona: {
					name: "United States",
					role: "Superpower",
					background:
						"Global hegemon with 5th Fleet in Bahrain, CENTCOM forward HQ at Al Udeid, and carrier strike groups in Arabian Sea",
					traits: ["assertive", "alliance-focused", "technologically superior"],
					objectives: [
						"Prevent Iranian nuclear breakout",
						"Protect Gulf oil transit",
						"Defend allies Israel and Saudi Arabia",
					],
				},
				memory: [],
				resources: { military: 95, economic: 88, political: 82, intelligence: 90 },
				relationships: {
					iran: { targetAgentId: "iran", alignment: -85, trust: 5, history: [] },
					israel: { targetAgentId: "israel", alignment: 90, trust: 88, history: [] },
					russia: { targetAgentId: "russia", alignment: -40, trust: 15, history: [] },
					china: { targetAgentId: "china", alignment: -30, trust: 20, history: [] },
					saudi: { targetAgentId: "saudi", alignment: 65, trust: 55, history: [] },
					houthis: { targetAgentId: "houthis", alignment: -80, trust: 0, history: [] },
					hezbollah: { targetAgentId: "hezbollah", alignment: -90, trust: 0, history: [] },
				},
				currentStrategy: "Maximum pressure 2.0 — sanctions enforcement and carrier deterrence",
				morale: 78,
				stability: 85,
				influence: { regions: {}, spread: 0.8, resistance: 0.7 },
				color: "#2255ff",
				position: { lat: 38.9, lng: -77.04 },
			},
			{
				id: "iran",
				partyId: "iran",
				persona: {
					name: "Iran",
					role: "Regional Power",
					background:
						"Theocratic state with IRGC proxy network spanning Lebanon, Iraq, Yemen, and Syria. Enriching uranium to 60% at Natanz and Fordow",
					traits: ["resilient", "proxy-warfare", "ideologically driven"],
					objectives: [
						"Regime survival",
						"Nuclear threshold capability",
						"Regional hegemony via Axis of Resistance",
					],
				},
				memory: [],
				resources: { military: 61, economic: 42, political: 65, intelligence: 70 },
				relationships: {
					usa: { targetAgentId: "usa", alignment: -90, trust: 3, history: [] },
					israel: { targetAgentId: "israel", alignment: -95, trust: 0, history: [] },
					russia: { targetAgentId: "russia", alignment: 55, trust: 40, history: [] },
					china: { targetAgentId: "china", alignment: 50, trust: 35, history: [] },
					houthis: { targetAgentId: "houthis", alignment: 85, trust: 65, history: [] },
					hezbollah: { targetAgentId: "hezbollah", alignment: 90, trust: 70, history: [] },
				},
				currentStrategy: "Asymmetric escalation via proxy activation and nuclear hedging",
				morale: 85,
				stability: 62,
				influence: { regions: {}, spread: 0.6, resistance: 0.8 },
				color: "#dd2244",
				position: { lat: 35.69, lng: 51.39 },
			},
			{
				id: "israel",
				partyId: "israel",
				persona: {
					name: "Israel",
					role: "Regional Ally",
					background:
						"US-aligned military power conducting active operations against Iran's nuclear program and proxy network. Struck Iranian territory in Oct 2024",
					traits: ["technologically advanced", "preemptive doctrine", "intelligence-focused"],
					objectives: [
						"Neutralize Iranian nuclear threat",
						"Degrade Hezbollah capability",
						"Maintain qualitative military edge",
					],
				},
				memory: [],
				resources: { military: 74, economic: 68, political: 60, intelligence: 88 },
				relationships: {
					usa: { targetAgentId: "usa", alignment: 90, trust: 85, history: [] },
					iran: { targetAgentId: "iran", alignment: -95, trust: 0, history: [] },
					russia: { targetAgentId: "russia", alignment: -20, trust: 18, history: [] },
					hezbollah: { targetAgentId: "hezbollah", alignment: -95, trust: 0, history: [] },
					saudi: { targetAgentId: "saudi", alignment: 40, trust: 30, history: [] },
				},
				currentStrategy: "Preemptive strikes on nuclear sites and proxy leadership",
				morale: 70,
				stability: 75,
				influence: { regions: {}, spread: 0.5, resistance: 0.6 },
				color: "#2255ff",
				position: { lat: 31.77, lng: 35.23 },
			},
			{
				id: "russia",
				partyId: "russia",
				persona: {
					name: "Russia",
					role: "Great Power",
					background:
						"Strategic competitor receiving Iranian Shahed drones for Ukraine war. Maintains naval base at Tartus, Syria and provides diplomatic cover at UNSC",
					traits: ["opportunistic", "arms dealer", "UN veto power"],
					objectives: ["Expand influence", "Sustain drone supply from Iran", "Counter US hegemony"],
				},
				memory: [],
				resources: { military: 83, economic: 52, political: 70, intelligence: 78 },
				relationships: {
					usa: { targetAgentId: "usa", alignment: -45, trust: 10, history: [] },
					iran: { targetAgentId: "iran", alignment: 55, trust: 38, history: [] },
					israel: { targetAgentId: "israel", alignment: -15, trust: 20, history: [] },
					china: { targetAgentId: "china", alignment: 60, trust: 45, history: [] },
				},
				currentStrategy: "S-400 deployment and diplomatic shielding at UNSC",
				morale: 72,
				stability: 68,
				influence: { regions: {}, spread: 0.6, resistance: 0.7 },
				color: "#9933cc",
				position: { lat: 55.75, lng: 37.62 },
			},
			{
				id: "china",
				partyId: "china",
				persona: {
					name: "China",
					role: "Economic Power",
					background:
						"Iran's largest oil buyer (sanctions evasion). Brokered 2023 Saudi-Iran deal. Energy dependency on Gulf region via Belt and Road",
					traits: ["economically focused", "non-interventionist", "Belt and Road"],
					objectives: ["Protect oil imports", "Mediate to prevent oil disruption", "Reduce US influence"],
				},
				memory: [],
				resources: { military: 78, economic: 95, political: 75, intelligence: 72 },
				relationships: {
					usa: { targetAgentId: "usa", alignment: -35, trust: 18, history: [] },
					iran: { targetAgentId: "iran", alignment: 48, trust: 32, history: [] },
					russia: { targetAgentId: "russia", alignment: 58, trust: 42, history: [] },
					saudi: { targetAgentId: "saudi", alignment: 35, trust: 28, history: [] },
				},
				currentStrategy: "Economic leverage and quiet diplomacy to keep oil flowing",
				morale: 80,
				stability: 88,
				influence: { regions: {}, spread: 0.7, resistance: 0.6 },
				color: "#ffaa00",
				position: { lat: 39.9, lng: 116.4 },
			},
			{
				id: "saudi",
				partyId: "saudi",
				persona: {
					name: "Saudi Arabia",
					role: "Regional Power",
					background:
						"Gulf oil superpower hedging between US alliance and Iran détente. Abraham Accords normalization paused after Gaza conflict",
					traits: ["oil leverage", "cautious diplomacy", "anti-Iran hedging"],
					objectives: ["Oil market stability", "Contain Iran", "Diversify alliances"],
				},
				memory: [],
				resources: { military: 65, economic: 92, political: 72, intelligence: 60 },
				relationships: {
					usa: { targetAgentId: "usa", alignment: 60, trust: 50, history: [] },
					iran: { targetAgentId: "iran", alignment: -50, trust: 15, history: [] },
					israel: { targetAgentId: "israel", alignment: 35, trust: 25, history: [] },
					houthis: { targetAgentId: "houthis", alignment: -85, trust: 0, history: [] },
				},
				currentStrategy: "Oil production leverage and defensive posture",
				morale: 75,
				stability: 82,
				influence: { regions: {}, spread: 0.5, resistance: 0.6 },
				color: "#2255ff",
				position: { lat: 24.71, lng: 46.68 },
			},
			{
				id: "houthis",
				partyId: "houthis",
				persona: {
					name: "Houthis",
					role: "Iran Proxy",
					background:
						"Ansar Allah movement controlling northern Yemen. Conducting anti-shipping campaign in Red Sea and Bab el-Mandeb since Nov 2023",
					traits: ["asymmetric warfare", "anti-ship missiles", "ideologically motivated"],
					objectives: [
						"Disrupt Red Sea shipping",
						"Force Israel-Gaza ceasefire",
						"Consolidate control of Yemen",
					],
				},
				memory: [],
				resources: { military: 40, economic: 15, political: 35, intelligence: 30 },
				relationships: {
					iran: { targetAgentId: "iran", alignment: 85, trust: 60, history: [] },
					usa: { targetAgentId: "usa", alignment: -90, trust: 0, history: [] },
					saudi: { targetAgentId: "saudi", alignment: -85, trust: 0, history: [] },
				},
				currentStrategy: "Red Sea shipping disruption with anti-ship missiles and drones",
				morale: 90,
				stability: 55,
				influence: { regions: {}, spread: 0.3, resistance: 0.9 },
				color: "#dd2244",
				position: { lat: 15.37, lng: 44.19 },
			},
			{
				id: "hezbollah",
				partyId: "hezbollah",
				persona: {
					name: "Hezbollah",
					role: "Iran Proxy",
					background:
						"Lebanese militant group severely degraded after 2024 Israeli campaign — leadership decapitated, infrastructure destroyed. Ceasefire in effect",
					traits: ["rocket arsenal", "tunnel warfare", "politically embedded"],
					objectives: [
						"Rebuild military capability",
						"Maintain political power in Lebanon",
						"Deter further Israeli strikes",
					],
				},
				memory: [],
				resources: { military: 35, economic: 20, political: 45, intelligence: 40 },
				relationships: {
					iran: { targetAgentId: "iran", alignment: 90, trust: 70, history: [] },
					israel: { targetAgentId: "israel", alignment: -95, trust: 0, history: [] },
					usa: { targetAgentId: "usa", alignment: -85, trust: 0, history: [] },
				},
				currentStrategy: "Reconstitution under ceasefire — rebuilding depleted arsenal",
				morale: 45,
				stability: 40,
				influence: { regions: {}, spread: 0.2, resistance: 0.7 },
				color: "#dd2244",
				position: { lat: 33.85, lng: 35.49 },
			},
		];

		const conflicts: Conflict[] = [
			{
				id: "strait-of-hormuz",
				name: "Strait of Hormuz",
				parties: ["usa", "iran"],
				location: { lat: 26.56, lng: 56.25 },
				intensity: 0.8,
				type: "conventional",
			},
			{
				id: "red-sea-shipping",
				name: "Red Sea / Bab el-Mandeb",
				parties: ["usa", "houthis", "iran"],
				location: { lat: 12.58, lng: 43.33 },
				intensity: 0.75,
				type: "hybrid",
			},
			{
				id: "natanz-nuclear",
				name: "Natanz Nuclear Facility",
				parties: ["israel", "iran", "usa"],
				location: { lat: 33.72, lng: 51.73 },
				intensity: 0.7,
				type: "cyber",
			},
			{
				id: "lebanon-ceasefire",
				name: "Lebanon Border",
				parties: ["israel", "hezbollah"],
				location: { lat: 33.27, lng: 35.2 },
				intensity: 0.4,
				type: "proxy",
			},
			{
				id: "syria-theater",
				name: "Syria Theater",
				parties: ["usa", "russia", "iran"],
				location: { lat: 33.51, lng: 38.67 },
				intensity: 0.5,
				type: "hybrid",
			},
			{
				id: "iraq-militias",
				name: "Iraq Militia Front",
				parties: ["usa", "iran"],
				location: { lat: 33.30, lng: 44.37 },
				intensity: 0.55,
				type: "proxy",
			},
			{
				id: "yemen-strikes",
				name: "Yemen (Sanaa)",
				parties: ["usa", "houthis"],
				location: { lat: 15.37, lng: 44.19 },
				intensity: 0.65,
				type: "conventional",
			},
		];

		const worldEvents: WorldEvent[] = [
			{
				turn: 47,
				timestamp: new Date(),
				type: "military",
				description:
					"IRGC deploys fast-attack boats and mines near Strait of Hormuz chokepoint",
				agentId: "iran",
				severity: "critical",
			},
			{
				turn: 47,
				timestamp: new Date(),
				type: "military",
				description: "USS Eisenhower CSG repositions to Arabian Sea; B-2s staged at Diego Garcia",
				agentId: "usa",
				severity: "high",
			},
			{
				turn: 47,
				timestamp: new Date(),
				type: "military",
				description: "Houthi anti-ship missile strikes container vessel in Bab el-Mandeb",
				agentId: "houthis",
				severity: "high",
			},
			{
				turn: 46,
				timestamp: new Date(),
				type: "intelligence",
				description:
					"IAEA confirms Iran enriching to 60% U-235 at Fordow — breakout time under 2 weeks",
				agentId: "iran",
				severity: "critical",
			},
			{
				turn: 46,
				timestamp: new Date(),
				type: "intelligence",
				description: "Mossad detects increased centrifuge activity at Natanz underground halls",
				agentId: "israel",
				severity: "critical",
			},
			{
				turn: 45,
				timestamp: new Date(),
				type: "economic",
				description: "Brent crude surges past $140/barrel; tanker insurance premiums spike 300%",
				severity: "high",
			},
			{
				turn: 45,
				timestamp: new Date(),
				type: "military",
				description: "Russia deploys additional S-400 battery to Tartus naval base, Syria",
				agentId: "russia",
				severity: "high",
			},
			{
				turn: 44,
				timestamp: new Date(),
				type: "diplomatic",
				description:
					"China brokers emergency backchannel talks between Tehran and Riyadh",
				agentId: "china",
				severity: "medium",
			},
			{
				turn: 44,
				timestamp: new Date(),
				type: "military",
				description:
					"Kata'ib Hezbollah launches rocket salvo at US forces at Al-Tanf base, Syria",
				agentId: "iran",
				severity: "high",
			},
			{
				turn: 43,
				timestamp: new Date(),
				type: "intelligence",
				description:
					"CIA intercepts IRGC communications indicating Hezbollah rearmament shipments via Syria",
				agentId: "usa",
				severity: "critical",
			},
			{
				turn: 43,
				timestamp: new Date(),
				type: "diplomatic",
				description: "Saudi Arabia raises oil output to offset Hormuz disruption fears",
				agentId: "saudi",
				severity: "medium",
			},
			{
				turn: 42,
				timestamp: new Date(),
				type: "economic",
				description: "China secures alternative oil pipeline through Pakistan to bypass Hormuz",
				agentId: "china",
				severity: "medium",
			},
		];

		const event: GlobalEvent = {
			id: "us-iran-2025",
			title: "US-Iran Conflict Escalation",
			description:
				"Multi-front confrontation between the US-Israel axis and Iran's Axis of Resistance, driven by nuclear breakout fears, Strait of Hormuz tensions, and Houthi Red Sea campaign.",
			category: "conflict",
			region: "Middle East",
			parties: [],
			context: {
				background:
					"Post-Oct 2023 escalation cycle: Hamas attack triggered Axis of Resistance activation. Iran-Israel direct strikes in Apr/Oct 2024 normalized state-on-state conflict. Trump maximum pressure 2.0 tightens sanctions.",
				triggers: [
					"Iran uranium enrichment at 60% near weapons-grade",
					"Houthi Red Sea shipping disruption",
					"Strait of Hormuz mine-laying incidents",
					"Proxy rocket attacks on US bases in Iraq and Syria",
				],
				stakes: [
					"Global oil supply (21% transits Hormuz)",
					"Nuclear proliferation threshold",
					"Regional power balance",
					"Freedom of navigation in Red Sea",
				],
				historicalPrecedents: [
					"1988 Operation Praying Mantis",
					"2020 Soleimani strike",
					"Apr 2024 Iran-Israel direct exchange",
					"Oct 2024 Israeli strikes on Iranian territory",
				],
			},
			createdAt: new Date(),
		};

		set({
			event,
			agents,
			conflicts,
			worldEvents,
			status: "running",
			turn: 47,
			globalTension: 82,
			agentReasoning: [],
			lastTurnActions: [],
			actionToasts: [],
			outcomePredictions: initialOutcomePredictions(),
		});
	},
}));

function initialOutcomePredictions(): OutcomePrediction[] {
	return [
		{
			outcome: "Negotiated Ceasefire",
			probability: 0.24,
			trend: "stable",
			rationale: "Baseline before the first Gemma 4 agent turn.",
		},
		{
			outcome: "Controlled Deterrence",
			probability: 0.31,
			trend: "stable",
			rationale: "Major actors are escalated but still signaling.",
		},
		{
			outcome: "Regional War",
			probability: 0.22,
			trend: "stable",
			rationale: "Proxy and maritime fronts are already active.",
		},
		{
			outcome: "Humanitarian Corridor",
			probability: 0.13,
			trend: "stable",
			rationale: "Requires diplomatic coordination across hostile actors.",
		},
		{
			outcome: "Oil Shock > 30 Days",
			probability: 0.1,
			trend: "stable",
			rationale: "Hormuz risk is elevated but not yet fully priced into the simulation.",
		},
	];
}

function buildOutcomePredictions(results: AgentTurnResult[], tension: number): OutcomePrediction[] {
	const previous = useSimulationStore.getState().outcomePredictions;
	const avgIntensity =
		results.reduce((acc, r) => acc + r.action.intensity, 0) / Math.max(results.length, 1);
	const diplomaticShare =
		results.filter((r) => r.action.type === "diplomatic" || r.action.type === "humanitarian").length /
		Math.max(results.length, 1);
	const militaryShare =
		results.filter((r) => r.action.type === "military" || r.action.type === "propaganda").length /
		Math.max(results.length, 1);
	const economicShare =
		results.filter((r) => r.action.type === "economic").length / Math.max(results.length, 1);

	const raw = [
		{
			outcome: "Negotiated Ceasefire",
			probability: clamp01((100 - tension) / 180 + diplomaticShare * 0.34),
			rationale: "Gemma 4 weighted fresh diplomatic and humanitarian actions against global tension.",
		},
		{
			outcome: "Controlled Deterrence",
			probability: clamp01(0.42 - Math.abs(avgIntensity - 0.45) * 0.45),
			rationale: "Moderate-intensity actions imply signaling without decisive escalation.",
		},
		{
			outcome: "Regional War",
			probability: clamp01(tension / 180 + militaryShare * 0.28),
			rationale: "Military and propaganda moves increase the probability of cross-front escalation.",
		},
		{
			outcome: "Humanitarian Corridor",
			probability: clamp01(diplomaticShare * 0.38 + (100 - tension) / 260),
			rationale: "Humanitarian feasibility improves when Gemma agents choose lower-intensity coordination.",
		},
		{
			outcome: "Oil Shock > 30 Days",
			probability: clamp01(tension / 220 + economicShare * 0.36 + militaryShare * 0.12),
			rationale: "Economic actions and maritime escalation push the oil-risk branch upward.",
		},
	];

	const total = raw.reduce((acc, item) => acc + item.probability, 0) || 1;
	return raw.map((item) => {
		const probability = item.probability / total;
		const prior = previous.find((p) => p.outcome === item.outcome)?.probability ?? probability;
		return {
			...item,
			probability,
			trend: probability > prior + 0.015 ? "up" : probability < prior - 0.015 ? "down" : "stable",
		};
	});
}

function clamp01(value: number) {
	return Math.max(0.02, Math.min(0.82, value));
}
