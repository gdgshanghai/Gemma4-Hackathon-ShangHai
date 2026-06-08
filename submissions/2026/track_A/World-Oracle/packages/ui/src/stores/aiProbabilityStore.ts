import { create } from "zustand";

interface AiProbabilityStore {
  probability: number;
  lastUpdated: Date | null;
  update: (probability: number) => void;
}

export const useAiProbabilityStore = create<AiProbabilityStore>((set) => ({
  probability: 0.78,
  lastUpdated: null,
  update: (probability) => set({ probability, lastUpdated: new Date() }),
}));
