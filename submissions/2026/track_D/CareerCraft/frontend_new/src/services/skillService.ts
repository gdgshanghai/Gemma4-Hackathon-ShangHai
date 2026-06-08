import { SkillNode } from '@/types';
import { skillTrees } from '@/data';
import { api } from './apiClient';
import { mergeBackendSkillsIntoTree, toBackendSkillId } from './apiAdapters';

export const skillService = {
  getSkillsByCareerId: async (careerId: string): Promise<SkillNode[]> => {
    const localSkills = skillTrees[careerId] || [];
    try {
      const profile = await api.fetchUserProfile();
      const backendSkills = profile.skills || [];
      if (!backendSkills.length) return localSkills;
      return mergeBackendSkillsIntoTree(localSkills, backendSkills);
    } catch (error) {
      console.warn('Skill API failed; using local skill tree fallback.', error);
      return localSkills;
    }
  },

  upgradeSkill: async (skillId: string, level: number, experience: number): Promise<void> => {
    await api.upgradeSkill(toBackendSkillId(skillId), level, experience);
  },
};

