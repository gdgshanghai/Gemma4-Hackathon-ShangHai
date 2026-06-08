import { Feedback } from '@/types';
import { skillTrees } from '@/data';
import { api } from './apiClient';
import { inferFrontendCareerId, mapExperienceGainsToFrontend } from './apiAdapters';
import { getCachedEvaluationResult } from './missionService';

export interface FeynmanChallengeState {
  careerId: string;
  active: boolean;
  question: string | null;
  missionFound: boolean;
}

function buildFeedbackFromEvaluation(
  missionId: string,
  feedbackText: string,
  gains: Record<string, number>,
  feynmanQuestion?: string | null,
): Feedback {
  const frontendGains = mapExperienceGainsToFrontend(gains || {});
  const skillNames = Object.values(skillTrees)
    .flat()
    .reduce<Record<string, string>>((acc, skill) => {
      acc[skill.id] = skill.name;
      return acc;
    }, {});
  const score = feedbackText.length > 42 ? 85 : 76;
  return {
    id: `feedback-${missionId}`,
    missionId,
    score,
    maxScore: 100,
    comment: feedbackText,
    strengths: ['Submission reviewed by backend evaluator', 'Core task reasoning is present'],
    improvements: feynmanQuestion
      ? ['Complete the Feynman challenge', feynmanQuestion]
      : ['Add more concrete evidence for the conclusion'],
    skillExpGained: Object.entries(frontendGains).map(([skillId, expGained]) => ({
      skillId: skillNames[skillId] || skillId,
      expGained,
    })),
    badgesEarned: ['Mission reviewed'],
    createdAt: new Date().toISOString(),
  };
}

export const feedbackService = {
  getFeedbackByMissionId: async (missionId: string): Promise<Feedback | undefined> => {
    const cached = getCachedEvaluationResult(missionId);
    if (cached) {
      return buildFeedbackFromEvaluation(
        missionId,
        cached.feedback,
        cached.experience_gains,
        cached.feynman_question,
      );
    }

    try {
      const profile = await api.fetchUserProfile();
      const mission = profile.missions.find((m) => m.mission_id === missionId);
      if (mission?.feedback) {
        return buildFeedbackFromEvaluation(
          missionId,
          mission.feedback,
          mission.experience_gains || {},
          mission.feynman_question,
        );
      }
      return undefined;
    } catch (err) {
      console.warn('Feedback API failed.', err);
      return undefined;
    }
  },

  submitFeynmanAnswer: async (
    missionId: string,
    answer: string,
    signal?: AbortSignal,
  ): Promise<{ status: string; feedback: string; mission_status?: string }> => {
    return api.submitFeynman(missionId, answer, signal);
  },

  getFeynmanChallenge: async (missionId: string): Promise<FeynmanChallengeState> => {
    const profile = await api.fetchUserProfile();
    const mission = profile.missions.find((item) => item.mission_id === missionId);
    const careerId = mission
      ? inferFrontendCareerId(mission.mission_id, {
          backendCareerId: mission.career_id,
          roleId: mission.role_id,
          fallbackCareerId: profile.user.current_career_id,
        })
      : profile.user.current_career_id || 'software-engineer';

    return {
      careerId,
      active: Boolean(mission?.feynman_question && mission.feynman_active),
      question: mission?.feynman_question || null,
      missionFound: Boolean(mission),
    };
  },
};
