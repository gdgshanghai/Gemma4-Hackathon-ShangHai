import { create } from "zustand";
import { getWarEndsProbability } from "../services/polymarket";

const DISABLE_POLYMARKET = import.meta.env.VITE_DISABLE_POLYMARKET !== "false";

interface PolymarketStore {
	probability: number | null;
	loading: boolean;
	error: string | null;
	lastUpdated: Date | null;
	sourceLabel: "PMKT" | "LIVE";
	headline: string;
	refresh: () => Promise<void>;
}

const DEMO_LIVE_SIGNALS = [
	{
		probability: 0.31,
		headline: "OSINT: China mediation channel reopened",
	},
	{
		probability: 0.28,
		headline: "Shipping AIS: Red Sea insurance remains elevated",
	},
	{
		probability: 0.34,
		headline: "Energy desk: Brent volatility easing after Gulf statement",
	},
	{
		probability: 0.26,
		headline: "Intel wire: proxy launch tempo still above baseline",
	},
];

let demoSignalIndex = 0;

export const usePolymarketStore = create<PolymarketStore>((set) => ({
	probability: null,
	loading: false,
	error: null,
	lastUpdated: null,
	sourceLabel: DISABLE_POLYMARKET ? "LIVE" : "PMKT",
	headline: DISABLE_POLYMARKET
		? "Local live-signal demo feed"
		: "Polymarket CLOB midpoint",

	refresh: async () => {
		if (DISABLE_POLYMARKET) {
			const signal = DEMO_LIVE_SIGNALS[demoSignalIndex % DEMO_LIVE_SIGNALS.length];
			demoSignalIndex += 1;
			set({
				probability: signal.probability,
				loading: false,
				error: null,
				lastUpdated: new Date(),
				sourceLabel: "LIVE",
				headline: signal.headline,
			});
			return;
		}
		set({ loading: true });
		try {
			const probability = await getWarEndsProbability();
			set({
				probability,
				loading: false,
				error: null,
				lastUpdated: new Date(),
				sourceLabel: "PMKT",
				headline: "Polymarket CLOB midpoint",
			});
		} catch (err) {
			const signal = DEMO_LIVE_SIGNALS[demoSignalIndex % DEMO_LIVE_SIGNALS.length];
			demoSignalIndex += 1;
			set({
				probability: signal.probability,
				loading: false,
				error: err instanceof Error ? err.message : "Fetch failed",
				lastUpdated: new Date(),
				sourceLabel: "LIVE",
				headline: `Fallback: ${signal.headline}`,
			});
		}
	},
}));

let timer: ReturnType<typeof setInterval> | null = null;

export function startPolymarketRefresh() {
	if (timer) return;
	const store = usePolymarketStore.getState();
	store.refresh();
	timer = setInterval(() => {
		usePolymarketStore.getState().refresh();
	}, 12_000);
}

export function stopPolymarketRefresh() {
	if (timer) {
		clearInterval(timer);
		timer = null;
	}
}
