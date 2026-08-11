import {
  ApiErrorSchema,
  DemoScenarioSchema,
  EveningResponseSchema,
  type DemoScenario,
  type EveningResponse,
} from "./contracts";

const EVENING_API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8040/api/v1/evenings";
const API_ROOT = EVENING_API_BASE.replace(/\/evenings\/?$/, "");

export class EveningApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly recovery?: EveningResponse,
  ) {
    super(message);
    this.name = "EveningApiError";
  }
}

async function readResponse(response: Response): Promise<EveningResponse> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new EveningApiError(response.status, "invalid_response", "服务返回了无法读取的数据。");
  }

  if (response.ok) {
    return EveningResponseSchema.parse(payload);
  }

  const parsedError = ApiErrorSchema.safeParse(payload);
  const recovery =
    response.status === 503
      ? EveningResponseSchema.safeParse(payload)
      : undefined;
  throw new EveningApiError(
    response.status,
    parsedError.success ? parsedError.data.error.code : "request_failed",
    parsedError.success ? parsedError.data.error.message : "请求没有完成。",
    recovery?.success ? recovery.data : undefined,
  );
}

async function get(path: string): Promise<EveningResponse> {
  const response = await fetch(`${EVENING_API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  return readResponse(response);
}

async function post(path: string, body: object): Promise<EveningResponse> {
  const response = await fetch(`${EVENING_API_BASE}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify(body),
  });
  return readResponse(response);
}

async function put(path: string, body: object): Promise<EveningResponse> {
  const response = await fetch(`${EVENING_API_BASE}${path}`, {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify(body),
  });
  return readResponse(response);
}

export function createEvening(input: {
  start_time: string;
  sleep_time: string;
}): Promise<EveningResponse> {
  return post("", { ...input, expected_version: 0 });
}

export function updateTimeBoundary(
  sessionId: string,
  version: number,
  startTime: string,
  sleepTime: string,
): Promise<EveningResponse> {
  return put(`/${encodeURIComponent(sessionId)}/time-boundary`, {
    start_time: startTime,
    sleep_time: sleepTime,
    expected_version: version,
  });
}

export async function getDemoScenario(): Promise<DemoScenario> {
  const response = await fetch(`${API_ROOT}/demo/scenario`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new EveningApiError(response.status, "demo_unavailable", "无法读取演示情景。");
  }
  return DemoScenarioSchema.parse(await response.json());
}

export async function resetDemoEvening(
  expectedSessionId: string | null,
): Promise<EveningResponse> {
  const response = await fetch(`${API_ROOT}/demo/evenings/today/reset`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({ expected_session_id: expectedSessionId }),
  });
  return readResponse(response);
}

export async function getTodayEvening(): Promise<EveningResponse | null> {
  try {
    return await get("/today");
  } catch (error) {
    if (error instanceof EveningApiError && error.status === 404) return null;
    throw error;
  }
}

export function getEvening(sessionId: string): Promise<EveningResponse> {
  return get(`/${encodeURIComponent(sessionId)}`);
}

export function addIntakeTurn(
  sessionId: string,
  version: number,
  text: string,
): Promise<EveningResponse> {
  return post(`/${encodeURIComponent(sessionId)}/intake-turns`, {
    text,
    expected_version: version,
  });
}

export function confirmInventory(
  sessionId: string,
  version: number,
): Promise<EveningResponse> {
  return post(`/${encodeURIComponent(sessionId)}/inventory/confirm`, {
    expected_version: version,
  });
}

export function createPlan(
  sessionId: string,
  version: number,
  reason: "initial" | "child_reorder" | "focus_pace" | "manual_deadline_risk",
  preferredOrder?: string[],
  deadlineRiskTaskIds: string[] = [],
): Promise<EveningResponse> {
  return post(`/${encodeURIComponent(sessionId)}/plans`, {
    expected_version: version,
    reason,
    ...(preferredOrder ? { preferred_order: preferredOrder } : {}),
    ...(deadlineRiskTaskIds.length ? { deadline_risk_task_ids: deadlineRiskTaskIds } : {}),
  });
}

export function commitPlan(
  sessionId: string,
  planId: string,
  version: number,
): Promise<EveningResponse> {
  return post(
    `/${encodeURIComponent(sessionId)}/plans/${encodeURIComponent(planId)}/commit`,
    { expected_version: version },
  );
}

export function closeEvening(
  sessionId: string,
  version: number,
  unfinishedTaskIds: string[],
  largestDeviation: { task_id: string; actual_minutes: number } | null,
  note: string | null,
): Promise<EveningResponse> {
  return post(`/${encodeURIComponent(sessionId)}/close-turns`, {
    expected_version: version,
    unfinished_task_ids: unfinishedTaskIds,
    largest_deviation: largestDeviation,
    note,
  });
}
