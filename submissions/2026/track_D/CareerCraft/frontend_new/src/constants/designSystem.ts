export type BadgeVariant = 
  | 'primary' 
  | 'success' 
  | 'warning' 
  | 'danger' 
  | 'neutral'
  | 'coming-soon';

export type StatusType = 
  | 'available' 
  | 'accepted' 
  | 'submitted' 
  | 'completed' 
  | 'locked' 
  | 'coming-soon' 
  | 'ai-thinking'
  | 'rag-hit'
  | 'feynman-pass';

export const COLORS = {
  primary: {
    base: '#6366f1', 
    dark: '#4338ca', 
    light: '#818cf8', 
  },
  success: {
    base: '#22c55e', 
    dark: '#15803d', 
    light: '#86efac', 
  },
  warning: {
    base: '#f59e0b', 
    dark: '#b45309', 
    light: '#fbbf24', 
  },
  danger: {
    base: '#ef4444', 
    dark: '#991b1b', 
    light: '#fca5a5', 
  },
  neutral: {
    base: '#64748b', 
    dark: '#334155', 
    light: '#94a3b8', 
  },
} as const;

export const BADGE_VARIANTS: Record<BadgeVariant, {
  bg: string;
  text: string;
  border: string;
  shadowDark: string;
  shadowLight: string;
}> = {
  primary: {
    bg: 'bg-indigo-600',
    text: 'text-white',
    border: 'border-indigo-800',
    shadowDark: '#3730a3',
    shadowLight: '#a5b4fc',
  },
  success: {
    bg: 'bg-green-600',
    text: 'text-white',
    border: 'border-green-800',
    shadowDark: '#166534',
    shadowLight: '#86efac',
  },
  warning: {
    bg: 'bg-amber-500',
    text: 'text-black',
    border: 'border-amber-700',
    shadowDark: '#b45309',
    shadowLight: '#fbbf24',
  },
  danger: {
    bg: 'bg-red-600',
    text: 'text-white',
    border: 'border-red-800',
    shadowDark: '#991b1b',
    shadowLight: '#fca5a5',
  },
  neutral: {
    bg: 'bg-slate-600',
    text: 'text-white',
    border: 'border-slate-800',
    shadowDark: '#1e293b',
    shadowLight: '#94a3b8',
  },
  'coming-soon': {
    bg: 'bg-slate-700',
    text: 'text-slate-400',
    border: 'border-slate-800',
    shadowDark: '#1e293b',
    shadowLight: '#475569',
  },
} as const;

export const STATUS_CONFIG: Record<StatusType, {
  label: string;
  badgeVariant: BadgeVariant;
  icon?: string;
}> = {
  'available': {
    label: '可领取',
    badgeVariant: 'success',
    icon: '✅',
  },
  'accepted': {
    label: '进行中',
    badgeVariant: 'warning',
    icon: '🔄',
  },
  'submitted': {
    label: '评审中',
    badgeVariant: 'primary',
    icon: '⏳',
  },
  'completed': {
    label: '已完成',
    badgeVariant: 'success',
    icon: '🎉',
  },
  'locked': {
    label: '未解锁',
    badgeVariant: 'neutral',
    icon: '🔒',
  },
  'coming-soon': {
    label: '即将开放',
    badgeVariant: 'coming-soon',
    icon: '⏳',
  },
  'ai-thinking': {
    label: 'AI 分析中',
    badgeVariant: 'primary',
    icon: '🤖',
  },
  'rag-hit': {
    label: '知识命中',
    badgeVariant: 'success',
    icon: '📚',
  },
  'feynman-pass': {
    label: '挑战通过',
    badgeVariant: 'success',
    icon: '🧠',
  },
} as const;

export const getStatusBadgeVariant = (status: StatusType): BadgeVariant => {
  return STATUS_CONFIG[status]?.badgeVariant || 'neutral';
};

export const getStatusLabel = (status: StatusType): string => {
  return STATUS_CONFIG[status]?.label || status;
};

export const BUTTON_VARIANTS = {
  primary: {
    bg: 'bg-indigo-600',
    text: 'text-white',
    shadowDark: '#3730a3',
    shadowLight: '#a5b4fc',
  },
  secondary: {
    bg: 'bg-slate-600',
    text: 'text-white',
    shadowDark: '#334155',
    shadowLight: '#94a3b8',
  },
  danger: {
    bg: 'bg-red-600',
    text: 'text-white',
    shadowDark: '#991b1b',
    shadowLight: '#fca5a5',
  },
  ghost: {
    bg: 'bg-transparent',
    text: 'text-indigo-400',
    shadowDark: 'none',
    shadowLight: 'none',
  },
} as const;

export const PROGRESS_COLORS = {
  primary: '#6366f1',
  success: '#22c55e',
  warning: '#f59e0b',
  danger: '#ef4444',
} as const;

export const ASSET_PATHS = {
  world: '/assets/world',
  islands: '/assets/islands',
  agents: '/assets/agents',
  rag: '/assets/rag',
  feynman: '/assets/feynman',
  badges: '/assets/badges',
  icons: '/assets/icons',
} as const;
