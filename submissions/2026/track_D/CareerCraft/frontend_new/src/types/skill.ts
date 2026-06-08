export interface SkillNode {
  id: string;
  name: string;
  description: string;
  level: number;
  maxLevel: number;
  exp: number;
  expToNext: number;
  unlocked: boolean;
  x: number;
  y: number;
  prerequisites: string[];
  children: string[];
}

export interface SkillTree {
  id: string;
  careerId: string;
  nodes: SkillNode[];
}
