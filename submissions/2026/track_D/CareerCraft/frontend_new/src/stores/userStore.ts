'use client';

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { api } from '@/services/apiClient';

interface UserStore {
  currentCareerId: string | null;
  totalXp: number;

  selectCareer: (careerId: string) => Promise<void>;
  addXp: (amount: number) => void;
  syncFromBackend: () => Promise<void>;
  isCareerActive: () => boolean;
}

export const useUserStore = create<UserStore>()(
  persist(
    (set, get) => ({
      currentCareerId: null,
      totalXp: 0,

      selectCareer: async (careerId: string) => {
        set({ currentCareerId: careerId });
        try {
          await api.updateCareer(careerId);
        } catch (error) {
          console.warn('Career selection was not saved to backend.', error);
          throw error;
        }
      },

      addXp: (amount: number) => {
        set((state) => ({ totalXp: state.totalXp + amount }));
      },

      syncFromBackend: async () => {
        try {
          const data = await api.fetchUserProfile();
          set({
            currentCareerId: data.user.current_career_id || null,
            totalXp: data.user.total_xp || 0,
          });
        } catch (error) {
          console.warn('User sync failed; keeping local cache.', error);
        }
      },

      isCareerActive: () => {
        return !!get().currentCareerId;
      },
    }),
    {
      name: 'careercraft-user-store',
      storage: createJSONStorage(() => localStorage),
    },
  ),
);

