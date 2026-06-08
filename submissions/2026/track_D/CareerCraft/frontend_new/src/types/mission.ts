export enum MissionStatus {
  LOCKED = 'locked',
  AVAILABLE = 'available',
  ACCEPTED = 'accepted',
  SUBMITTED = 'submitted',
  COMPLETED = 'completed',
}

export interface Mission {
  id: string;
  careerId?: string;
  title: string;
  description: string;
  background: string;
  objectives: string[];
  deliverables: string[];
  criteria: string[];
  difficulty: 'easy' | 'medium' | 'hard';
  status: MissionStatus;
  rewardExp: number;
  rewardSkills: string[];
  mockDataUrl?: string;
  deadline?: string;
  taskDirection?: string | null;
  missionStyle?: string | null;
  aiLead?: string;
  recommendedResources?: string[];
  estimatedTime?: string;
}
