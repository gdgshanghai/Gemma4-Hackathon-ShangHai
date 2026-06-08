import { Mission, MissionStatus, SkillNode } from '@/types';

export type ApiDataSource = 'api' | 'fallback' | 'error';

type Difficulty = Mission['difficulty'];

export interface CareerApiConfig {
  frontendCareerId: string;
  backendCareerId: string;
  missionRoleId?: string;
  resourceDomain: string;
  apiSupported: boolean;
}

export interface BackendMissionLike {
  mission_id: string;
  career_id?: string | null;
  role_id?: string | null;
  title: string;
  description: string;
  mock_data_url?: string | null;
  delivery_requirements?: string[] | null;
  difficulty?: string | null;
  status?: string | null;
  reward_xp?: number | null;
  reward_skills?: string[] | null;
  evaluation_criteria?: string[] | null;
  task_direction?: string | null;
  mission_style?: string | null;
  display_metadata?: {
    ai_lead?: string | null;
    business_background?: string | null;
    objectives?: string[] | null;
    recommended_skills?: string[] | null;
    recommended_resources?: string[] | null;
    estimated_time?: string | null;
  } | null;
  feedback?: string | null;
  feynman_active?: boolean | null;
  experience_gains?: Record<string, number> | null;
}

export interface BackendSkillProgressLike {
  skill_id: string;
  level: number;
  experience: number;
}

export const CAREER_API_CONFIGS: Record<string, CareerApiConfig> = {
  'data-analyst': {
    frontendCareerId: 'data-analyst',
    backendCareerId: 'career_data_analyst',
    missionRoleId: 'mentor_ying',
    resourceDomain: 'core_data',
    apiSupported: true,
  },
  'software-engineer': {
    frontendCareerId: 'software-engineer',
    backendCareerId: 'career_software_engineer',
    missionRoleId: 'mentor_ling',
    resourceDomain: 'core_software',
    apiSupported: true,
  },
  'product-designer': {
    frontendCareerId: 'product-designer',
    backendCareerId: 'career_product_designer',
    resourceDomain: 'core_product',
    apiSupported: false,
  },
  'ai-researcher': {
    frontendCareerId: 'ai-researcher',
    backendCareerId: 'career_ai_researcher',
    resourceDomain: 'core_ai',
    apiSupported: false,
  },
};

const BACKEND_TO_FRONTEND_CAREER_ID = Object.fromEntries(
  Object.values(CAREER_API_CONFIGS).map((item) => [item.backendCareerId, item.frontendCareerId]),
);

const ROLE_TO_FRONTEND_CAREER_ID: Record<string, string> = Object.fromEntries(
  Object.values(CAREER_API_CONFIGS)
    .filter((item) => item.missionRoleId)
    .map((item) => [item.missionRoleId as string, item.frontendCareerId]),
);

const BACKEND_TO_FRONTEND_SKILL_ID: Record<string, string> = {
  skill_data_cleaning: 'da-clean',
  skill_data_quality: 'da-clean',
  skill_exploratory_analysis: 'da-desc',
  skill_business_insight: 'da-conv',
  skill_data_storytelling: 'da-report',
  skill_strategic_recommendation: 'da-report',
  skill_stakeholder_mgmt: 'da-report',
  skill_kpi_system_design: 'da-conv',
  skill_dashboard_design: 'da-visual',
  skill_drill_down_analysis: 'da-desc',
  skill_root_cause_analysis: 'da-conv',
  skill_debugging: 'se-debug',
  skill_unit_testing: 'se-test',
  skill_code_quality: 'se-quality',
  skill_api_design: 'se-api',
  skill_communication: 'se-comm',
  skill_refactoring: 'se-quality',
  skill_software_design: 'se-api',
  skill_perf_troubleshooting: 'se-log',
  skill_sql_optimization: 'se-log',
  skill_incident_response: 'se-log',
};

const FRONTEND_TO_BACKEND_SKILL_ID: Record<string, string> = {
  'da-clean': 'skill_data_cleaning',
  'da-sql': 'skill_drill_down_analysis',
  'da-desc': 'skill_exploratory_analysis',
  'da-conv': 'skill_business_insight',
  'da-visual': 'skill_dashboard_design',
  'da-report': 'skill_data_storytelling',
  'se-debug': 'skill_debugging',
  'se-test': 'skill_unit_testing',
  'se-api': 'skill_api_design',
  'se-log': 'skill_perf_troubleshooting',
  'se-quality': 'skill_code_quality',
  'se-comm': 'skill_communication',
};

const DEFAULT_CRITERIA = [
  'Problem understanding is clear',
  'Deliverables are complete',
  'Recommendations are actionable',
];

const DEFAULT_ESTIMATED_TIME: Record<Difficulty, string> = {
  easy: '20-30 min',
  medium: '40-60 min',
  hard: '60-90 min',
};

export function toBackendCareerId(careerId: string): string {
  return CAREER_API_CONFIGS[careerId]?.backendCareerId ?? careerId;
}

export function toFrontendCareerId(careerId: string | null | undefined): string | null {
  if (!careerId) return null;
  return BACKEND_TO_FRONTEND_CAREER_ID[careerId] ?? careerId;
}

export function toMissionRoleId(careerOrRoleId: string): string {
  return CAREER_API_CONFIGS[careerOrRoleId]?.missionRoleId ?? careerOrRoleId;
}

export function resourceDomainForCareer(careerId: string): string {
  return CAREER_API_CONFIGS[careerId]?.resourceDomain ?? 'core_data';
}

export function toBackendSkillId(skillId: string): string {
  return FRONTEND_TO_BACKEND_SKILL_ID[skillId] ?? skillId;
}

export function toFrontendSkillId(skillId: string): string {
  return BACKEND_TO_FRONTEND_SKILL_ID[skillId] ?? skillId;
}

export function mapExperienceGainsToFrontend(gains: Record<string, number>): Record<string, number> {
  return Object.entries(gains).reduce<Record<string, number>>((acc, [skillId, amount]) => {
    const frontendId = toFrontendSkillId(skillId);
    acc[frontendId] = (acc[frontendId] || 0) + amount;
    return acc;
  }, {});
}

export function inferFrontendCareerId(
  missionId: string | null | undefined,
  options: {
    backendCareerId?: string | null;
    roleId?: string | null;
    fallbackCareerId?: string | null;
  } = {},
): string {
  const fromBackendCareer = toFrontendCareerId(options.backendCareerId);
  if (fromBackendCareer) return fromBackendCareer;
  if (options.roleId && ROLE_TO_FRONTEND_CAREER_ID[options.roleId]) {
    return ROLE_TO_FRONTEND_CAREER_ID[options.roleId];
  }
  if (missionId?.startsWith('mvp_mission_data_')) return 'data-analyst';
  if (missionId?.startsWith('mvp_mission_software_')) return 'software-engineer';
  const fallback = toFrontendCareerId(options.fallbackCareerId);
  return fallback || 'data-analyst';
}

export function normalizeDifficulty(value: string | null | undefined): Difficulty {
  if (value === 'hard') return 'hard';
  if (value === 'easy') return 'easy';
  return 'medium';
}

export function mapBackendMissionStatus(
  mission: Pick<BackendMissionLike, 'status' | 'feedback' | 'feynman_active'>,
  options: { includeFailedAsLocked?: boolean } = {},
): MissionStatus | null {
  if (mission.status === MissionStatus.LOCKED) return MissionStatus.LOCKED;
  if (mission.status === MissionStatus.AVAILABLE) return MissionStatus.AVAILABLE;
  if (mission.status === MissionStatus.ACCEPTED) return MissionStatus.ACCEPTED;
  if (mission.status === MissionStatus.SUBMITTED) return MissionStatus.SUBMITTED;
  if (mission.status === MissionStatus.COMPLETED || mission.status === 'completed') return MissionStatus.COMPLETED;
  if (mission.status === 'failed') return options.includeFailedAsLocked ? MissionStatus.LOCKED : null;
  if (mission.status === 'active') {
    return mission.feedback || mission.feynman_active ? MissionStatus.SUBMITTED : MissionStatus.ACCEPTED;
  }
  return MissionStatus.AVAILABLE;
}

export function mapBackendMissionToMission(
  mission: BackendMissionLike,
  fallbackCareerId?: string | null,
  options: { includeFailedAsLocked?: boolean } = {},
): Mission | null {
  const status = mapBackendMissionStatus(mission, options);
  if (!status) return null;
  const careerId = inferFrontendCareerId(mission.mission_id, {
    backendCareerId: mission.career_id,
    roleId: mission.role_id,
    fallbackCareerId,
  });
  const rewardSkills = (mission.reward_skills && mission.reward_skills.length > 0)
    ? mission.reward_skills.map(toFrontendSkillId)
    : Object.keys(mapExperienceGainsToFrontend(mission.experience_gains || {}));
  const metadata = mission.display_metadata || {};
  const difficulty = normalizeDifficulty(mission.difficulty);
  const deliveryRequirements = mission.delivery_requirements || [];
  const objectives = metadata.objectives?.length ? metadata.objectives : deliveryRequirements;
  return {
    id: mission.mission_id,
    careerId,
    title: mission.title,
    description: mission.description,
    background: metadata.business_background || mission.description,
    objectives,
    deliverables: deliveryRequirements,
    criteria: mission.evaluation_criteria?.length ? mission.evaluation_criteria : DEFAULT_CRITERIA,
    difficulty,
    status,
    rewardExp: mission.reward_xp ?? 150,
    rewardSkills,
    mockDataUrl: mission.mock_data_url || undefined,
    taskDirection: mission.task_direction ?? null,
    missionStyle: mission.mission_style ?? null,
    aiLead: metadata.ai_lead || undefined,
    recommendedResources: metadata.recommended_resources || [],
    estimatedTime: metadata.estimated_time || DEFAULT_ESTIMATED_TIME[difficulty],
  };
}

export function mergeBackendSkillsIntoTree(
  localSkills: SkillNode[],
  backendSkills: BackendSkillProgressLike[],
): SkillNode[] {
  const byFrontendId = backendSkills.reduce<Record<string, { level: number; experience: number }>>(
    (acc, item) => {
      const frontendId = toFrontendSkillId(item.skill_id);
      const existing = acc[frontendId] || { level: 0, experience: 0 };
      acc[frontendId] = {
        level: Math.max(existing.level, item.level || 0),
        experience: existing.experience + (item.experience || 0),
      };
      return acc;
    },
    {},
  );

  return localSkills.map((skill) => {
    const backendSkill = byFrontendId[skill.id];
    if (!backendSkill) return skill;
    return {
      ...skill,
      level: Math.max(skill.level, backendSkill.level),
      exp: backendSkill.experience,
      unlocked: skill.unlocked || backendSkill.level > 0 || backendSkill.experience > 0,
    };
  });
}
