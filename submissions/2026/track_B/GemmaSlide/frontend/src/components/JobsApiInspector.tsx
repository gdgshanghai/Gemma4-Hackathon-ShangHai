import { type FormEvent, useRef, useState } from "react";

import {
  buildApiEndpoint,
  getPptxScriptJobResult,
  getPptxScriptJobStatus,
  submitPptxScriptJob,
} from "../api";
import type { PptxScriptSseEvent } from "../types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function JobsApiInspector() {
  const [submitFile, setSubmitFile] = useState<File | null>(null);
  const [includeImagesBase64, setIncludeImagesBase64] = useState(true);
  const [flattenGroups, setFlattenGroups] = useState(true);
  const [elementTypesInput, setElementTypesInput] = useState("");
  const [llmModel, setLlmModel] = useState("");

  const [jobId, setJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [submitResponse, setSubmitResponse] = useState<unknown>(null);
  const [statusResponse, setStatusResponse] = useState<unknown>(null);
  const [resultResponse, setResultResponse] = useState<unknown>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);

  function stopStream(): void {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setStreaming(false);
  }

  function appendEvent(line: string): void {
    setEvents((current) => [line, ...current].slice(0, 100));
  }

  async function onSubmitJob(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!submitFile) {
      setError("Choose a file before submitting a job.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const elementTypes = elementTypesInput
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean);

      const response = await submitPptxScriptJob(submitFile, {
        includeImagesBase64,
        flattenGroups,
        elementTypes,
        llmModel,
      });
      setSubmitResponse(response);
      setJobId(response.job_id);
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "Failed to submit job.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onFetchStatus(): Promise<void> {
    if (!jobId.trim()) {
      setError("Provide a job_id first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await getPptxScriptJobStatus(jobId.trim());
      setStatusResponse(response);
    } catch (statusError) {
      setError(
        statusError instanceof Error
          ? statusError.message
          : "Failed to fetch job status.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onFetchResult(): Promise<void> {
    if (!jobId.trim()) {
      setError("Provide a job_id first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await getPptxScriptJobResult(jobId.trim());
      setResultResponse(response);
    } catch (resultError) {
      setError(
        resultError instanceof Error
          ? resultError.message
          : "Failed to fetch job result.",
      );
    } finally {
      setBusy(false);
    }
  }

  function onStartStream(): void {
    if (!jobId.trim()) {
      setError("Provide a job_id first.");
      return;
    }

    stopStream();
    setError(null);
    setEvents([]);

    const url = buildApiEndpoint(`/api/v1/jobs/${jobId.trim()}/events`);
    const source = new EventSource(url);
    eventSourceRef.current = source;
    setStreaming(true);

    source.addEventListener("status", (event) => {
      try {
        const payload = JSON.parse(
          (event as MessageEvent).data,
        ) as PptxScriptSseEvent;
        appendEvent(
          `status v${payload.status.version}: ${payload.status.status}`,
        );
      } catch {
        appendEvent(`status: ${(event as MessageEvent).data}`);
      }
    });

    source.addEventListener("heartbeat", (event) => {
      appendEvent(`heartbeat: ${(event as MessageEvent).data}`);
    });

    source.addEventListener("done", (event) => {
      appendEvent(`done: ${(event as MessageEvent).data}`);
      stopStream();
    });

    source.onerror = () => {
      appendEvent("stream error/closed");
      stopStream();
    };
  }

  return (
    <Card className="mb-5">
      <CardContent className="p-5 md:p-6">
        <h2 className="text-xl font-semibold text-foreground">
          Jobs API Inspector
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Test endpoints under /api/v1/jobs and inspect raw API responses.
        </p>

        <form
          onSubmit={onSubmitJob}
          className="mt-4 grid gap-3 md:grid-cols-12"
        >
          <div className="md:col-span-4">
            <label className="mb-1 block text-sm font-medium">PPTX file</label>
            <Input
              type="file"
              accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
              onChange={(event) =>
                setSubmitFile(event.target.files?.[0] ?? null)
              }
              className="cursor-pointer file:mr-3 file:rounded-full file:border-0 file:bg-secondary file:px-4 file:py-2 file:text-xs file:font-medium file:text-secondary-foreground"
            />
          </div>

          <div className="md:col-span-4">
            <label className="mb-1 block text-sm font-medium">
              element_types
            </label>
            <Input
              type="text"
              value={elementTypesInput}
              onChange={(event) => setElementTypesInput(event.target.value)}
              placeholder="picture,text_box"
            />
          </div>

          <div className="md:col-span-2">
            <label className="mb-1 block text-sm font-medium">llm_model</label>
            <Input
              type="text"
              value={llmModel}
              onChange={(event) => setLlmModel(event.target.value)}
              placeholder="optional"
            />
          </div>

          <div className="md:col-span-2">
            <label className="mb-1 block text-sm font-medium">Submit</label>
            <Button type="submit" disabled={busy} className="w-full">
              POST /jobs/pptx-script
            </Button>
          </div>

          <label className="inline-flex items-center gap-2 text-sm md:col-span-3">
            <input
              type="checkbox"
              checked={includeImagesBase64}
              onChange={(event) => setIncludeImagesBase64(event.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            include_images_base64
          </label>

          <label className="inline-flex items-center gap-2 text-sm md:col-span-3">
            <input
              type="checkbox"
              checked={flattenGroups}
              onChange={(event) => setFlattenGroups(event.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            flatten_groups
          </label>
        </form>

        <div className="mt-4 grid gap-3 md:grid-cols-12">
          <div className="md:col-span-6">
            <label className="mb-1 block text-sm font-medium">job_id</label>
            <Input
              type="text"
              value={jobId}
              onChange={(event) => setJobId(event.target.value)}
              placeholder="Paste job_id"
            />
          </div>

          <div className="flex flex-wrap items-end gap-2 md:col-span-6">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={onFetchStatus}
            >
              GET /jobs/{"{job_id}"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={onFetchResult}
            >
              GET /jobs/{"{job_id}"}/result
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={streaming}
              onClick={onStartStream}
            >
              Start SSE
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!streaming}
              onClick={stopStream}
            >
              Stop SSE
            </Button>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-[16px] border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div>
            <p className="mb-1 text-sm font-medium">Submit response</p>
            <pre className="max-h-56 overflow-auto rounded-[16px] bg-muted p-3 text-xs">
              {submitResponse ? prettyJson(submitResponse) : "(empty)"}
            </pre>
          </div>

          <div>
            <p className="mb-1 text-sm font-medium">Status response</p>
            <pre className="max-h-56 overflow-auto rounded-[16px] bg-muted p-3 text-xs">
              {statusResponse ? prettyJson(statusResponse) : "(empty)"}
            </pre>
          </div>

          <div>
            <p className="mb-1 text-sm font-medium">Result response</p>
            <pre className="max-h-56 overflow-auto rounded-[16px] bg-muted p-3 text-xs">
              {resultResponse ? prettyJson(resultResponse) : "(empty)"}
            </pre>
          </div>

          <div>
            <p className="mb-1 text-sm font-medium">
              SSE events {streaming ? "(live)" : ""}
            </p>
            <pre className="max-h-56 overflow-auto rounded-[16px] bg-muted p-3 text-xs">
              {events.length > 0 ? events.join("\n") : "(empty)"}
            </pre>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
