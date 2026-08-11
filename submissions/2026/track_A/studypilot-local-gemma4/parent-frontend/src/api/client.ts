import { z } from "zod";

import {
  ApiErrorEnvelopeSchema,
  CalibrationResponseSchema,
  DemoScenarioSchema,
  EveningResultSchema,
  SchoolBriefReadEnvelopeSchema,
  SchoolBriefWriteEnvelopeSchema,
  WeeklySummaryEnvelopeSchema,
  type ApiErrorEnvelope,
  type CalibrationResponse,
  type DemoScenario,
  type EveningResult,
  type SchoolBriefRevision,
  type SchoolBriefWriteEnvelope,
  type SimplifiedDurationGroup,
  type WeeklySummaryEnvelope,
} from "./contracts";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8040/api/v1";

export async function getDemoScenario(): Promise<DemoScenario> {
  return request("/demo/scenario", DemoScenarioSchema);
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly envelope: ApiErrorEnvelope,
  ) {
    super(envelope.error.message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });
  const body: unknown = await response.json();
  if (!response.ok) {
    throw new ApiError(response.status, ApiErrorEnvelopeSchema.parse(body));
  }
  return schema.parse(body);
}

function postHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "Idempotency-Key": crypto.randomUUID(),
  };
}

export async function getSchoolBrief(briefDate: string): Promise<SchoolBriefRevision | null> {
  try {
    const envelope = await request(
      `/school-briefs?${new URLSearchParams({ brief_date: briefDate })}`,
      SchoolBriefReadEnvelopeSchema,
    );
    return envelope.data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function saveSchoolBrief(input: {
  briefDate: string;
  rawText: string;
  expectedRevision: number;
}): Promise<SchoolBriefWriteEnvelope> {
  return request("/school-briefs", SchoolBriefWriteEnvelopeSchema, {
    method: "POST",
    headers: postHeaders(),
    body: JSON.stringify({
      brief_date: input.briefDate,
      raw_text: input.rawText,
      expected_revision: input.expectedRevision,
    }),
  });
}

export function getWeeklySummary(weekStart: string): Promise<WeeklySummaryEnvelope> {
  return request(
    `/parent/weekly-summary?${new URLSearchParams({ week_start: weekStart })}`,
    WeeklySummaryEnvelopeSchema,
  );
}

export async function getLatestEvening(sessionDate: string): Promise<EveningResult | null> {
  try {
    return await request(
      `/evenings/latest?${new URLSearchParams({ session_date: sessionDate })}`,
      EveningResultSchema,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function getCalibration(calibrationId: string): Promise<CalibrationResponse> {
  return request(`/parent/calibrations/${encodeURIComponent(calibrationId)}`, CalibrationResponseSchema);
}

export function createCalibration(input: {
  text: string;
  expectedProfileVersion: number;
}): Promise<CalibrationResponse> {
  return request("/parent/calibrations", CalibrationResponseSchema, {
    method: "POST",
    headers: postHeaders(),
    body: JSON.stringify({
      text: input.text,
      expected_calibration_version: 0,
      expected_profile_version: input.expectedProfileVersion,
    }),
  });
}

export function retryCalibration(
  calibrationId: string,
  expectedCalibrationVersion: number,
): Promise<CalibrationResponse> {
  return request(
    `/parent/calibrations/${encodeURIComponent(calibrationId)}/retry`,
    CalibrationResponseSchema,
    {
      method: "POST",
      headers: postHeaders(),
      body: JSON.stringify({ expected_calibration_version: expectedCalibrationVersion }),
    },
  );
}

export function simplifyCalibration(input: {
  calibrationId: string;
  expectedCalibrationVersion: number;
  durationGroups: SimplifiedDurationGroup[];
}): Promise<CalibrationResponse> {
  return request(
    `/parent/calibrations/${encodeURIComponent(input.calibrationId)}/simplify`,
    CalibrationResponseSchema,
    {
      method: "POST",
      headers: postHeaders(),
      body: JSON.stringify({
        expected_calibration_version: input.expectedCalibrationVersion,
        duration_groups: input.durationGroups,
      }),
    },
  );
}

export function commitCalibration(input: {
  calibrationId: string;
  expectedCalibrationVersion: number;
  draftId: string;
  draftDigest: string;
  acceptedOperationIds: string[];
}): Promise<CalibrationResponse> {
  return request(
    `/parent/calibrations/${encodeURIComponent(input.calibrationId)}/commit`,
    CalibrationResponseSchema,
    {
      method: "POST",
      headers: postHeaders(),
      body: JSON.stringify({
        expected_calibration_version: input.expectedCalibrationVersion,
        draft_id: input.draftId,
        draft_digest: input.draftDigest,
        accepted_operation_ids: input.acceptedOperationIds,
      }),
    },
  );
}

export function abandonCalibration(
  calibrationId: string,
  expectedCalibrationVersion: number,
): Promise<CalibrationResponse> {
  return request(
    `/parent/calibrations/${encodeURIComponent(calibrationId)}/abandon`,
    CalibrationResponseSchema,
    {
      method: "POST",
      headers: postHeaders(),
      body: JSON.stringify({ expected_calibration_version: expectedCalibrationVersion }),
    },
  );
}
