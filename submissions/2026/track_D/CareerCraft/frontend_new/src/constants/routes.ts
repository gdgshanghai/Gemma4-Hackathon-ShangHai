export const ROUTES = {
  HOME: '/',
  LOBBY: '/lobby',
  PORTFOLIO: '/portfolio',
  COMMUNITY: '/community',
  CAREER: (id: string) => `/career/${id}`,
  MISSION: (id: string) => `/mission/${id}`,
  MISSION_SUBMIT: (id: string) => `/mission/${id}/submit`,
  MISSION_FEEDBACK: (id: string) => `/mission/${id}/feedback`
};
