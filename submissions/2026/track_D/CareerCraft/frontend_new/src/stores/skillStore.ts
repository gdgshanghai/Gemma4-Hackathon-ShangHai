'use client';

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { SkillNode } from '@/types';
import { skillService } from '@/services/skillService';

interface SkillStore {
  skills: SkillNode[];
  
  setSkills: (skills: SkillNode[]) => void;
  upgradeSkill: (skillId: string) => Promise<void>;
  addExperienceGains: (gains: Record<string, number>) => void;
  syncFromBackend: () => Promise<void>;
  isSkillUnlocked: (skillId: string) => boolean;
  getSkillById: (skillId: string) => SkillNode | undefined;
}

export const useSkillStore = create<SkillStore>()(
  persist(
    (set, get) => ({
      skills: [],

      setSkills: (skills: SkillNode[]) => {
        set({ skills });
      },

      upgradeSkill: async (skillId: string) => {
        const target = get().skills.find((skill) => skill.id === skillId);
        if (!target || target.exp < target.expToNext || target.level >= target.maxLevel) {
          return;
        }

        const newLevel = target.level + 1;
        const newExp = target.exp - target.expToNext;
        await skillService.upgradeSkill(skillId, newLevel, newExp);

        set(state => {
          const skills = state.skills.map(skill => {
            if (skill.id === skillId) {
              return {
                ...skill,
                level: newLevel,
                exp: newExp,
                expToNext: Math.round(skill.expToNext * 1.3),
              };
            }
            return skill;
          });
          return { skills };
        });
      },

      addExperienceGains: (gains: Record<string, number>) => {
        set(state => {
          const skills = state.skills.map(skill => {
            const gain = gains[skill.id];
            if (gain) {
              return { ...skill, exp: skill.exp + gain };
            }
            return skill;
          });
          return { skills };
        });
      },

      syncFromBackend: async () => {
        // 技能同步由 skillService 在加载时处理，此处无需额外调用
      },

      isSkillUnlocked: (skillId: string) => {
        const skill = get().skills.find(s => s.id === skillId);
        if (!skill) return false;
        if (!skill.prerequisites || skill.prerequisites.length === 0) return true;
        return skill.prerequisites.every(prereqId => {
          const prereq = get().skills.find(s => s.id === prereqId);
          return prereq ? prereq.level > 0 : false;
        });
      },

      getSkillById: (skillId: string) => {
        return get().skills.find(s => s.id === skillId);
      },
    }),
    {
      name: 'careercraft-skill-store',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
