const PLAYER_ID_STORAGE_KEY = 'careercraft.player_id';

export type AuthMode = 'anonymous' | 'account';

export interface IdentitySnapshot {
  mode: AuthMode;
  playerId: string;
}

function createPlayerId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

export function getPlayerId(): string | null {
  if (typeof window === 'undefined') return null;

  const existing = window.localStorage.getItem(PLAYER_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const created = createPlayerId();
  window.localStorage.setItem(PLAYER_ID_STORAGE_KEY, created);
  return created;
}

export function resetPlayerId(): string | null {
  if (typeof window === 'undefined') return null;

  const created = createPlayerId();
  window.localStorage.setItem(PLAYER_ID_STORAGE_KEY, created);
  return created;
}

export function getIdentitySnapshot(): IdentitySnapshot | null {
  const playerId = getPlayerId();
  if (!playerId) return null;

  return {
    mode: 'anonymous',
    playerId,
  };
}

export function getAuthHeaders(): Record<string, string> {
  const identity = getIdentitySnapshot();
  if (!identity) return {};

  return {
    'X-Player-Id': identity.playerId,
  };
}
