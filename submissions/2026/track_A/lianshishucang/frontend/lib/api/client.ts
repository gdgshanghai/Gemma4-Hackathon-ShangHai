const DEFAULT_API_BASE_URL = 'http://localhost:8080';

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  token?: string;
}

export function getApiBaseUrl(): string {
  const envUrl =
    typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL
      ? String(import.meta.env.VITE_API_BASE_URL)
      : '';

  return (envUrl || DEFAULT_API_BASE_URL).replace(/\/$/, '');
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  options: ApiClientOptions = {},
): Promise<T> {
  const baseUrl = (options.baseUrl || getApiBaseUrl()).replace(/\/$/, '');
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
  const headers = new Headers(init.headers ?? {});

  if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (options.token) {
    headers.set('Authorization', `Bearer ${options.token}`);
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  const payload = await parseResponse(response);

  if (!response.ok) {
    const message = extractErrorMessage(payload) || `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractErrorMessage(payload: unknown): string | null {
  if (!payload) {
    return null;
  }

  if (typeof payload === 'string') {
    return payload;
  }

  if (typeof payload === 'object' && payload !== null && 'error' in payload) {
    const error = (payload as { error?: unknown }).error;
    return typeof error === 'string' ? error : null;
  }

  return null;
}
