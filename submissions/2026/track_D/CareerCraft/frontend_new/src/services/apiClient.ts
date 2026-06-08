import { getAuthHeaders, resetPlayerId } from './identity';
import { toBackendCareerId, toFrontendCareerId } from './apiAdapters';

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ||
  'http://localhost:8000';

const DEFAULT_TIMEOUT_MS = 3*60000;
const MISSION_GENERATION_TIMEOUT_MS = 10 * 60000;
const AI_REVIEW_TIMEOUT_MS = 5 * 60000;

export class AbortError extends Error {
  constructor(message: string = 'Request was cancelled') {
    super(message);
    this.name = 'AbortError';
  }
}

export class ApiError extends Error {
  status?: number;
  path: string;
  fallbackAllowed: boolean;

  constructor(
    message: string,
    options: {
      path: string;
      status?: number;
      fallbackAllowed?: boolean;
    }
  ) {
    super(message);
    this.name = 'ApiError';
    this.path = options.path;
    this.status = options.status;
    this.fallbackAllowed = options.fallbackAllowed ?? true;
  }
}

type ApiRequestInit = RequestInit & {
  timeoutMs?: number;
  fallbackAllowed?: boolean;
  skipAuthRetry?: boolean;
};

const pendingRequests = new Map<string, AbortController>();

function getRequestKey(path: string, options: RequestInit = {}): string {
  const method = options.method || 'GET';
  const body = typeof options.body === 'string' ? options.body : '';
  return `${method}:${path}:${body}`;
}

function linkAbortSignals(
  controller: AbortController,
  signal?: AbortSignal
): () => void {
  // 只在客户端环境中使用
  if (typeof window === 'undefined') return () => {};
  if (!signal) return () => {};

  if (signal.aborted) {
    controller.abort(signal.reason);
    return () => {};
  }

  const onAbort = () => controller.abort(signal.reason);
  signal.addEventListener('abort', onAbort, { once: true });
  return () => signal.removeEventListener('abort', onAbort);
}

function withAuthHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers);
  Object.entries(getAuthHeaders()).forEach(([key, value]) => {
    merged.set(key, value);
  });
  return merged;
}

async function readErrorCode(res: Response): Promise<string | null> {
  try {
    const body = await res.clone().json();
    const detail = body?.detail;
    return typeof detail === 'object' && detail !== null && typeof detail.code === 'string'
      ? detail.code
      : null;
  } catch {
    return null;
  }
}

async function fetchWithAuthRetry(
  url: string,
  init: RequestInit,
  skipAuthRetry = false,
): Promise<Response> {
  const res = await fetch(url, {
    ...init,
    headers: withAuthHeaders(init.headers),
  });

  if (res.status !== 401 || skipAuthRetry) {
    return res;
  }

  const code = await readErrorCode(res);
  if (code === 'identity.invalid_player_id') {
    resetPlayerId();
  } else if (code !== 'identity.missing_player_id') {
    return res;
  }

  return fetch(url, {
    ...init,
    headers: withAuthHeaders(init.headers),
  });
}

export function abortPendingRequest(
  path: string,
  options: RequestInit = {}
): void {
  // 只在客户端环境中运行
  if (typeof window === 'undefined') return;
  
  const key = getRequestKey(path, options);
  const controller = pendingRequests.get(key);
  if (controller) {
    controller.abort();
    pendingRequests.delete(key);
  }
}

export function abortAllRequests(): void {
  // 只在客户端环境中运行
  if (typeof window === 'undefined') return;
  
  pendingRequests.forEach((controller) => controller.abort());
  pendingRequests.clear();
}

async function request<T>(
  path: string,
  options: ApiRequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  console.log('apiClient: request to:', url);
  const controller = new AbortController();
  const key = getRequestKey(path, options);
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const fallbackAllowed = options.fallbackAllowed ?? true;
  const skipAuthRetry = options.skipAuthRetry ?? false;
  
  // 只在客户端环境中使用 AbortController 和 timeout
  let unlinkExternalAbort: () => void = () => {};
  let timeoutId: any = null;
  
  if (typeof window !== 'undefined') {
    unlinkExternalAbort = linkAbortSignals(
      controller,
      options.signal ?? undefined
    );

    timeoutId = window.setTimeout(() => {
      controller.abort(`timeout:${timeoutMs}`);
    }, timeoutMs);

    pendingRequests.set(key, controller);
  }

  try {
    console.log('apiClient: Starting fetch to:', url);
    const {
      timeoutMs: _timeoutMs,
      fallbackAllowed: _fallbackAllowed,
      skipAuthRetry: _skipAuthRetry,
      ...fetchOptions
    } = options;
    const headers = new Headers(fetchOptions.headers);
    headers.set('Accept', 'application/json');
    if (typeof fetchOptions.body === 'string' && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const res = await fetchWithAuthRetry(url, {
      ...fetchOptions,
      signal: controller.signal,
      headers,
    }, skipAuthRetry);

    console.log('apiClient: Got response status:', res.status);
    if (!res.ok) {
      throw new ApiError(`API ${path} returned ${res.status}`, {
        path,
        status: res.status,
        fallbackAllowed,
      });
    }

    const json = await res.json();
    console.log('apiClient: Response JSON:', json);
    return json;
  } catch (err) {
    console.log('apiClient: Error:', err);
    // 服务端渲染时不抛出 AbortError，直接返回错误
    if (typeof window !== 'undefined' && err instanceof Error && err.name === 'AbortError') {
      throw new AbortError(`Request cancelled: ${path}`);
    }

    if (err instanceof ApiError) {
      throw err;
    }

    throw new ApiError(`API ${path} failed`, {
      path,
      fallbackAllowed,
    });
  } finally {
    if (typeof window !== 'undefined') {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      unlinkExternalAbort();
      pendingRequests.delete(key);
    }
  }
}

export async function streamChat(
  roleName: string,
  message: string,
  onChunk: (char: string) => void,
  abortSignal?: AbortSignal
): Promise<string> {
  const controller = new AbortController();
  let unlinkExternalAbort: () => void = () => {};
  let timeoutId: any = null;
  
  // 只在客户端环境中使用 AbortController 和 timeout
  if (typeof window !== 'undefined') {
    unlinkExternalAbort = linkAbortSignals(controller, abortSignal);
    timeoutId = window.setTimeout(() => {
      controller.abort(`timeout:${DEFAULT_TIMEOUT_MS}`);
    }, DEFAULT_TIMEOUT_MS);
  }

  try {
    const url = `${BASE_URL}/api/v1/agent/chat?role_name=${encodeURIComponent(
      roleName
    )}&message=${encodeURIComponent(message)}`;
    const response = await fetchWithAuthRetry(url, {
      signal: controller.signal,
      headers: { Accept: 'text/event-stream' },
    }, true);

    if (!response.ok) throw new ApiError('Agent chat connection failed', { path: '/api/v1/agent/chat' });
    if (!response.body) throw new ApiError('Stream not supported', { path: '/api/v1/agent/chat' });

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let fullText = '';
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const frame = buffer.substring(0, boundary);
        buffer = buffer.substring(boundary + 2);
        const lines = frame.split('\n');
        for (const line of lines) {
          if (line.startsWith('data:')) {
            let payload = line.substring(5);
            if (payload.startsWith(' ')) payload = payload.substring(1);
            if (payload) {
              fullText += payload;
              onChunk(payload);
            }
          }
        }
        boundary = buffer.indexOf('\n\n');
      }
    }
    return fullText;
  } catch (err) {
    if (typeof window !== 'undefined' && err instanceof Error && err.name === 'AbortError') {
      throw new AbortError('Agent chat stream was cancelled');
    }
    throw err;
  } finally {
    if (typeof window !== 'undefined') {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      unlinkExternalAbort();
    }
  }
}

export const api = {
  async checkHealth(signal?: AbortSignal): Promise<boolean> {
    try {
      const res = await request<{ status: string }>('/', { signal, timeoutMs: 5000 });
      return res.status === 'healthy';
    } catch {
      return false;
    }
  },

  async fetchCareers(signal?: AbortSignal): Promise<BackendCareer[]> {
    return request<BackendCareer[]>('/api/v1/careers', { signal });
  },

  async searchKnowledgeBase(
    query: string,
    domain: string,
    signal?: AbortSignal
  ): Promise<Resource[]> {
    const url = `/api/v1/careers/resources?query=${encodeURIComponent(query)}&domain=${encodeURIComponent(domain)}`;
    return request<Resource[]>(url, { signal });
  },

  async generateMission(
    roleId: string,
    difficulty: string = 'easy',
    taskDirection?: string | null,
    missionStyle?: string | null,
    signal?: AbortSignal
  ): Promise<GeneratedMission> {
    return request<GeneratedMission>('/api/v1/missions/generate', {
      method: 'POST',
      body: JSON.stringify({
        role_id: roleId,
        difficulty,
        task_direction: taskDirection ?? null,
        mission_style: missionStyle ?? null,
      }),
      signal,
      timeoutMs: MISSION_GENERATION_TIMEOUT_MS,
      fallbackAllowed: false,
    });
  },

  async evaluateSubmission(
    missionId: string,
    submissionText: string,
    signal?: AbortSignal
  ): Promise<EvaluationResult> {
    return request<EvaluationResult>('/api/v1/missions/evaluate', {
      method: 'POST',
      body: JSON.stringify({ mission_id: missionId, submission_text: submissionText }),
      signal,
      timeoutMs: AI_REVIEW_TIMEOUT_MS,
      fallbackAllowed: false,
    });
  },

  async fetchUserProfile(signal?: AbortSignal): Promise<UserSyncData> {
    const data = await request<UserSyncData>('/api/v1/user/sync', { signal });
    return {
      ...data,
      user: {
        ...data.user,
        current_career_id: toFrontendCareerId(data.user.current_career_id),
      },
    };
  },

  async updateCareer(
    careerId: string,
    signal?: AbortSignal
  ): Promise<{ status: string; current_career_id: string }> {
    const data = await request<{ status: string; current_career_id: string }>('/api/v1/user/career', {
      method: 'POST',
      body: JSON.stringify({ career_id: toBackendCareerId(careerId) }),
      signal,
    });
    return {
      ...data,
      current_career_id: toFrontendCareerId(data.current_career_id) ?? '',
    };
  },

  async upgradeSkill(
    skillId: string,
    level: number,
    experience: number,
    signal?: AbortSignal
  ): Promise<{ status: string }> {
    return request('/api/v1/user/skills/upgrade', {
      method: 'POST',
      body: JSON.stringify({ skill_id: skillId, level, experience }),
      signal,
      fallbackAllowed: false,
    });
  },

  async submitFeynman(
    missionId: string,
    answer: string,
    signal?: AbortSignal
  ): Promise<{ status: string; feedback: string; mission_status?: string }> {
    return request('/api/v1/user/feynman/submit', {
      method: 'POST',
      body: JSON.stringify({ mission_id: missionId, answer }),
      signal,
      timeoutMs: AI_REVIEW_TIMEOUT_MS,
      fallbackAllowed: false,
    });
  },
};

export interface BackendCareer {
  career_id: string;
  name: string;
  description: string;
  unlocked: boolean;
  role_id?: string | null;
  resource_domain?: string | null;
  api_supported?: boolean;
}

export interface Resource {
  doc_id: string;
  title: string;
  snippet: string;
  relevance_score: number;
  source?: string | null;
  tags?: string[];
}

export interface GeneratedMission {
  mission_id: string;
  career_id?: string | null;
  role_id?: string | null;
  title: string;
  description: string;
  mock_data_url: string;
  delivery_requirements: string[];
  difficulty?: string;
  task_direction?: string | null;
  mission_style?: string | null;
  status?: string;
  reward_xp?: number;
  reward_skills?: string[];
  evaluation_criteria?: string[];
  display_metadata?: MissionDisplayMetadata | null;
}

export interface MissionDisplayMetadata {
  ai_lead?: string | null;
  business_background?: string | null;
  objectives?: string[] | null;
  recommended_skills?: string[] | null;
  recommended_resources?: string[] | null;
  estimated_time?: string | null;
}

export interface EvaluationResult {
  status: string;
  feedback: string;
  experience_gains: Record<string, number>;
  trigger_feynman_challenge: boolean;
  feynman_question: string | null;
  mission_status?: string | null;
  feynman_active?: boolean | null;
}

export interface UserSyncData {
  user: {
    id: string;
    current_career_id: string | null;
    total_xp: number;
  };
  skills: {
    skill_id: string;
    level: number;
    experience: number;
  }[];
  missions: {
    mission_id: string;
    title: string;
    description: string;
    mock_data_url: string;
    delivery_requirements: string[];
    career_id?: string | null;
    role_id?: string | null;
    difficulty?: string | null;
    task_direction?: string | null;
    mission_style?: string | null;
    reward_xp?: number | null;
    reward_skills?: string[] | null;
    evaluation_criteria?: string[] | null;
    display_metadata?: MissionDisplayMetadata | null;
    status: string;
    submission_text: string | null;
    feedback: string | null;
    experience_gains: Record<string, number>;
    feynman_active: boolean;
    feynman_question: string | null;
    feynman_answer: string | null;
    feynman_feedback: string | null;
  }[];
}
