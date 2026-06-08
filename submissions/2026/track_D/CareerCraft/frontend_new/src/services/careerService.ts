import { CareerIsland } from '@/types';
import { careerIslands } from '@/data';
import { api, AbortError, BackendCareer } from './apiClient';
import { CAREER_API_CONFIGS, toFrontendCareerId } from './apiAdapters';

export type CareerDataSource = 'api' | 'fallback';
export type CareerIslandApiView = CareerIsland & {
  unlocked: boolean;
  roleId?: string | null;
  resourceDomain?: string | null;
  apiSupported: boolean;
};

function withDefaultUnlockState(items: CareerIsland[]): CareerIslandApiView[] {
  return items.map((island) => ({
    ...island,
    unlocked: island.careers.some((career) => career.unlocked),
    roleId: CAREER_API_CONFIGS[island.id]?.missionRoleId ?? null,
    resourceDomain: CAREER_API_CONFIGS[island.id]?.resourceDomain ?? null,
    apiSupported: CAREER_API_CONFIGS[island.id]?.apiSupported ?? false,
  }));
}

export const careerService = {
  getAllCareerIslandsWithSource: async (): Promise<{ data: CareerIslandApiView[]; source: CareerDataSource }> => {
    try {
      const backendCareers: BackendCareer[] = await api.fetchCareers();
      if (!backendCareers.length) {
        return { data: withDefaultUnlockState(careerIslands), source: 'fallback' };
      }
      const data = careerIslands.map((island) => {
        const match = backendCareers.find((item) => toFrontendCareerId(item.career_id) === island.id);
        return match
          ? {
              ...island,
              name: match.name || island.name,
              description: match.description || island.description,
              unlocked: match.unlocked,
              roleId: match.role_id ?? CAREER_API_CONFIGS[island.id]?.missionRoleId ?? null,
              resourceDomain: match.resource_domain ?? CAREER_API_CONFIGS[island.id]?.resourceDomain ?? null,
              apiSupported: match.api_supported ?? CAREER_API_CONFIGS[island.id]?.apiSupported ?? true,
            }
          : {
              ...island,
              unlocked: island.careers.some((career) => career.unlocked),
              roleId: CAREER_API_CONFIGS[island.id]?.missionRoleId ?? null,
              resourceDomain: CAREER_API_CONFIGS[island.id]?.resourceDomain ?? null,
              apiSupported: false,
            };
      });
      return { data, source: 'api' };
    } catch (error) {
      if (error instanceof AbortError) throw error;
      console.warn('Career list API unavailable, using local fallback data.', error);
      return { data: withDefaultUnlockState(careerIslands), source: 'fallback' };
    }
  },

  getAllCareerIslands: async (): Promise<CareerIsland[]> => {
    const { data } = await careerService.getAllCareerIslandsWithSource();
    return data;
  },

  getCareerIslandById: async (id: string): Promise<CareerIsland | undefined> => {
    const fallback = careerIslands.find((island) => island.id === id);
    if (!fallback) return undefined;
    try {
      return (await careerService.getAllCareerIslands()).find((island) => island.id === id) || fallback;
    } catch (error) {
      if (error instanceof AbortError) throw error;
      return fallback;
    }
  },
};
