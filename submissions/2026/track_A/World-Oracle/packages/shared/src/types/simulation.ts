import type { AgentAction, AgentState } from "./agent.js";
import type { GlobalEvent } from "./event.js";

export type SimulationStatus =
	| "extracting"
	| "initializing"
	| "running"
	| "paused"
	| "completed";

export interface InfluenceCell {
	lat: number;
	lng: number;
	influences: Record<string, number>; // agentId → intensity 0-1
}

export interface InfluenceGrid {
	resolution: number;
	cells: InfluenceCell[];
}

export interface Conflict {
	id: string;
	name: string;
	parties: string[];
	location: { lat: number; lng: number };
	intensity: number; // 0-1
	type: "conventional" | "proxy" | "cyber" | "economic" | "hybrid";
}

export interface WorldEvent {
	turn: number;
	timestamp: Date;
	type: string;
	description: string;
	agentId?: string;
	severity: "low" | "medium" | "high" | "critical";
}

export interface WorldState {
	turn: number;
	date: Date;
	activeConflicts: Conflict[];
	influenceGrid: InfluenceGrid;
	events: WorldEvent[];
	globalTension: number; // 0-100
}

export interface SimulationTurn {
	turn: number;
	actions: AgentAction[];
	worldState: WorldState;
	events: WorldEvent[];
}

export interface SimulationResult {
	outcome: string;
	winner?: string;
	probability: number;
	endDate: Date;
	keyTurningPoints: { turn: number; description: string }[];
	alternativeOutcomes: { outcome: string; probability: number }[];
}

export interface Simulation {
	id: string;
	event: GlobalEvent;
	agents: AgentState[];
	worldState: WorldState;
	turns: SimulationTurn[];
	status: SimulationStatus;
	result?: SimulationResult;
}
