import { create } from "zustand";

export type GlobeLayer =
	| "military"
	| "economic"
	| "diplomatic"
	| "propaganda"
	| "conflicts"
	| "alliances"
	| "sanctions"
	| "influence";

interface GlobeStore {
	activeLayers: Set<GlobeLayer>;
	selectedCountry: string | null;
	selectedAgentId: string | null;
	cameraTarget: { lat: number; lng: number } | null;
	zoom: number;

	toggleLayer: (layer: GlobeLayer) => void;
	setSelectedCountry: (country: string | null) => void;
	setSelectedAgent: (agentId: string | null) => void;
	setCameraTarget: (target: { lat: number; lng: number } | null) => void;
	setZoom: (zoom: number) => void;
}

export const useGlobeStore = create<GlobeStore>((set) => ({
	activeLayers: new Set<GlobeLayer>(["military", "conflicts", "influence"]),
	selectedCountry: null,
	selectedAgentId: null,
	cameraTarget: null,
	zoom: 2.5,

	toggleLayer: (layer) =>
		set((s) => {
			const next = new Set(s.activeLayers);
			if (next.has(layer)) next.delete(layer);
			else next.add(layer);
			return { activeLayers: next };
		}),
	setSelectedCountry: (country) => set({ selectedCountry: country }),
	setSelectedAgent: (agentId) => set({ selectedAgentId: agentId }),
	setCameraTarget: (target) => set({ cameraTarget: target }),
	setZoom: (zoom) => set({ zoom }),
}));
