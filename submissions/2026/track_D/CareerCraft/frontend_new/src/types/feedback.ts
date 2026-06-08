export interface Feedback {
  id: string;
  missionId: string;
  score: number;
  maxScore: number;
  comment: string;
  strengths: string[];
  improvements: string[];
  skillExpGained: {
    skillId: string;
    expGained: number;
  }[];
  badgesEarned: string[];
  createdAt: string;
}
