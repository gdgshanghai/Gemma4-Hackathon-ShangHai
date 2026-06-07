import type {
  BranchGenerateRequest,
  BranchMatchResult,
  BranchNode,
  BranchTreeResponse,
} from "./types";
import type {
  ParsePptxResponse,
  PrecomputedBranchesResponse,
  PresentationScriptResult,
  PptxScriptJobStatus,
  PptxScriptJobSubmitResponse,
} from "./types";

export interface ParseOptions {
  includeImagesBase64: boolean;
  flattenGroups: boolean;
  elementTypes: string[];
}

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? "";

export function buildApiEndpoint(path: string): string {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL.replace(/\/$/, "")}${path}`;
}

export async function parsePptx(
  file: File,
  options: ParseOptions,
): Promise<ParsePptxResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const params = new URLSearchParams();
  params.set("include_images_base64", String(options.includeImagesBase64));
  params.set("flatten_groups", String(options.flattenGroups));

  for (const elementType of options.elementTypes) {
    params.append("element_types", elementType);
  }

  const endpoint = buildApiEndpoint(
    `/api/v1/debug/pptx/parse?${params.toString()}`,
  );
  const response = await fetch(endpoint, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        detail = body.detail;
      }
    } catch {
      // Keep the default error message when the response has no JSON body.
    }
    throw new Error(`Failed to parse PPTX: ${detail}`);
  }

  return (await response.json()) as ParsePptxResponse;
}

interface SubmitPptxScriptJobOptions {
  includeImagesBase64: boolean;
  flattenGroups: boolean;
  elementTypes: string[];
  llmModel?: string;
}

function toQueryString(params: URLSearchParams): string {
  const query = params.toString();
  return query.length > 0 ? `?${query}` : "";
}

export async function submitPptxScriptJob(
  file: File,
  options: SubmitPptxScriptJobOptions,
): Promise<PptxScriptJobSubmitResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const params = new URLSearchParams();
  params.set("include_images_base64", String(options.includeImagesBase64));
  params.set("flatten_groups", String(options.flattenGroups));
  for (const elementType of options.elementTypes) {
    params.append("element_types", elementType);
  }
  if (options.llmModel && options.llmModel.trim().length > 0) {
    params.set("llm_model", options.llmModel.trim());
  }

  const endpoint = buildApiEndpoint(
    `/api/v1/jobs/pptx-script${toQueryString(params)}`,
  );
  const response = await fetch(endpoint, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to submit job: ${response.status} ${detail}`);
  }

  return (await response.json()) as PptxScriptJobSubmitResponse;
}

export async function parsePptxOnly(
  file: File,
  options: ParseOptions,
): Promise<ParsePptxResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const params = new URLSearchParams();
  params.set("include_images_base64", String(options.includeImagesBase64));
  params.set("flatten_groups", String(options.flattenGroups));
  for (const elementType of options.elementTypes) {
    params.append("element_types", elementType);
  }

  const endpoint = buildApiEndpoint(
    `/api/v1/jobs/pptx/parse-only${toQueryString(params)}`,
  );
  const response = await fetch(endpoint, { method: "POST", body: formData });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to parse PPTX: ${response.status} ${detail}`);
  }

  return (await response.json()) as ParsePptxResponse;
}

export async function getPptxScriptJobStatus(
  jobId: string,
): Promise<PptxScriptJobStatus> {
  const endpoint = buildApiEndpoint(`/api/v1/jobs/${jobId}`);
  const response = await fetch(endpoint);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to fetch status: ${response.status} ${detail}`);
  }
  return (await response.json()) as PptxScriptJobStatus;
}

export async function getPptxScriptJobResult(
  jobId: string,
): Promise<PresentationScriptResult> {
  const endpoint = buildApiEndpoint(`/api/v1/jobs/${jobId}/result`);
  const response = await fetch(endpoint);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to fetch result: ${response.status} ${detail}`);
  }
  return (await response.json()) as PresentationScriptResult;
}

export async function generateBranches(
  req: BranchGenerateRequest,
): Promise<BranchTreeResponse> {
  const endpoint = buildApiEndpoint("/api/v1/branches");
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      `Failed to generate branches: ${response.status} ${detail}`,
    );
  }

  return (await response.json()) as BranchTreeResponse;
}

export async function fetchPrecomputedBranches(
  parseId: string,
): Promise<PrecomputedBranchesResponse> {
  const endpoint = buildApiEndpoint(`/api/v1/branches/${parseId}`);
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new Error(`Failed to fetch branches: ${response.status}`);
  }
  return (await response.json()) as PrecomputedBranchesResponse;
}

export interface BranchSseCallbacks {
  onBranchReady: (slideIndex: number, branches: BranchNode[]) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

/**
 * Connect to the branch precomputation SSE stream.
 *
 * Instead of polling GET /branches/{parseId}, open ONE long-lived connection
 * that pushes branch_ready events as each slide is computed, then a final
 * done event. Falls back to polling if SSE fails after a few retries.
 */
export async function streamBranchEvents(
  parseId: string,
  callbacks: BranchSseCallbacks,
  signal: AbortSignal,
): Promise<void> {
  const url = buildApiEndpoint(`/api/v1/branches/${parseId}/events`);

  let retries = 0;
  const maxRetries = 3;

  while (retries < maxRetries) {
    if (signal.aborted) return;

    try {
      const response = await fetch(url, {
        headers: { Accept: "text/event-stream" },
        signal,
      });

      if (!response.ok) {
        if (response.status === 404) {
          callbacks.onError(`Parse cache not found: ${parseId}`);
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (!signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });

        let idx: number;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const rawEvent = buf.slice(0, idx);
          buf = buf.slice(idx + 2);

          const eventType = rawEvent.match(/^event:\s*(.+)$/m)?.[1]?.trim();
          const dataLine = rawEvent.match(/^data:\s*(.+)$/m)?.[1]?.trim();

          if (!eventType || !dataLine) continue;

          try {
            const data = JSON.parse(dataLine);
            if (eventType === "branch_ready") {
              const branches = (data.branches ?? []).map(
                (b: Record<string, unknown>) => ({
                  branch_id: b.branch_id as string,
                  predicted_text: b.predicted_text as string,
                  action: b.action as BranchNode["action"],
                  teleprompter: b.teleprompter as string,
                  next_branches: (b.next_branches ?? []) as BranchNode[],
                }),
              );
              callbacks.onBranchReady(data.slide_index as number, branches);
            } else if (eventType === "done") {
              callbacks.onDone();
              return; // Success
            }
          } catch {
            // Skip malformed events
          }
        }
      }

      // Stream ended without "done" — may be normal if we got all events
      return;
    } catch (err) {
      if (signal.aborted) return;
      retries++;
      if (retries >= maxRetries) {
        callbacks.onError(
          `SSE failed after ${maxRetries} retries: ${err instanceof Error ? err.message : String(err)}`,
        );
        return;
      }
      // Exponential backoff before retry
      await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, retries)));
    }
  }
}

export async function matchBranchText(
  parseId: string,
  slideIndex: number,
  text: string,
): Promise<{ match: BranchMatchResult | null }> {
  const endpoint = buildApiEndpoint(`/api/v1/branches/${parseId}/match`);
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slide_index: slideIndex, text }),
  });
  if (!response.ok) {
    throw new Error(`Failed to match branch: ${response.status}`);
  }
  return (await response.json()) as { match: BranchMatchResult | null };
}
