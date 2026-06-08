import { create } from "zustand";

interface UIStore {
	sidebarCollapsed: boolean;
	rightPanelCollapsed: boolean;
	bottomPanelCollapsed: boolean;
	activeRightTab: "intel" | "predictions";
	activeBottomTab: "reasoning" | "timeline";
	showEventInput: boolean;

	toggleSidebar: () => void;
	toggleRightPanel: () => void;
	toggleBottomPanel: () => void;
	setActiveRightTab: (tab: "intel" | "predictions") => void;
	setActiveBottomTab: (tab: "reasoning" | "timeline") => void;
	setShowEventInput: (show: boolean) => void;
}

export const useUIStore = create<UIStore>((set) => ({
	sidebarCollapsed: false,
	rightPanelCollapsed: false,
	bottomPanelCollapsed: false,
	activeRightTab: "intel",
	activeBottomTab: "reasoning",
	showEventInput: false,

	toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
	toggleRightPanel: () => set((s) => ({ rightPanelCollapsed: !s.rightPanelCollapsed })),
	toggleBottomPanel: () => set((s) => ({ bottomPanelCollapsed: !s.bottomPanelCollapsed })),
	setActiveRightTab: (tab) => set({ activeRightTab: tab }),
	setActiveBottomTab: (tab) => set({ activeBottomTab: tab }),
	setShowEventInput: (show) => set({ showEventInput: show }),
}));
