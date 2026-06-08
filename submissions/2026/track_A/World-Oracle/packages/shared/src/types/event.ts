export type EventCategory = "conflict" | "diplomacy" | "economic" | "climate" | "technology";
export type PartyType = "nation" | "organization" | "militia" | "corporation" | "leader";
export type PartyRole = "primary" | "ally" | "adversary" | "neutral" | "mediator";

export interface Capabilities {
	military: number;
	economic: number;
	diplomatic: number;
	intelligence: number;
	cyber: number;
	nuclear: boolean;
}

export interface EventParty {
	id: string;
	name: string;
	type: PartyType;
	role: PartyRole;
	capabilities: Capabilities;
	goals: string[];
	flagEmoji?: string;
}

export interface EventContext {
	background: string;
	triggers: string[];
	stakes: string[];
	historicalPrecedents: string[];
}

export interface GlobalEvent {
	id: string;
	title: string;
	description: string;
	category: EventCategory;
	region: string;
	parties: EventParty[];
	context: EventContext;
	createdAt: Date;
}
