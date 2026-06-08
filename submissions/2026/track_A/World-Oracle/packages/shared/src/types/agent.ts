export interface AgentPersona {
	name: string;
	role: string;
	background: string;
	traits: string[];
	objectives: string[];
}

export interface AgentMemory {
	turn: number;
	type: "observation" | "action" | "reflection" | "communication";
	content: string;
	importance: number;
}

export interface ResourcePool {
	military: number;
	economic: number;
	political: number;
	intelligence: number;
}

export interface RelationshipState {
	targetAgentId: string;
	alignment: number; // -100 (hostile) to 100 (allied)
	trust: number; // 0-100
	history: string[];
}

export interface InfluenceMap {
	regions: Record<string, number>; // region → influence 0-100
	spread: number; // rate of spread
	resistance: number; // resistance to counter-influence
}

export interface AgentState {
	id: string;
	partyId: string;
	persona: AgentPersona;
	memory: AgentMemory[];
	resources: ResourcePool;
	relationships: Record<string, RelationshipState>;
	currentStrategy: string;
	morale: number;
	stability: number;
	influence: InfluenceMap;
	color: string; // hex color for visualization
	position: { lat: number; lng: number };
}

export type ActionType =
	| "military"
	| "diplomatic"
	| "economic"
	| "intelligence"
	| "propaganda"
	| "humanitarian";

export interface AgentAction {
	agentId: string;
	turn: number;
	type: ActionType;
	target: string;
	intensity: number;
	description: string;
	reasoning: string;
}
