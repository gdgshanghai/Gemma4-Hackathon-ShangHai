import { useEffect, useRef, useState } from "react";
import { buildApiEndpoint } from "../api";

/**
 * SSE connection state exposed to the UI.
 * - connecting:   first connect or reconnecting after a drop
 * - connected:    stream is actively pushing events
 * - disconnected: no active connection (job done, error, or idle)
 */
export type ConnectionState = "connecting" | "connected" | "disconnected";

export interface UseJobSseCallbacks {
  onStatus: (data: string) => void;
  onSlideReady: (data: string) => void;
  onDone: (data: string) => void;
}

/**
 * A custom SSE hook that uses fetch() + ReadableStream so we have full
 * control over reconnection.  Features:
 *
 *  - Exponential back-off: 1 s, 2 s, 4 s, 8 s, 16 s (capped).
 *  - Stops reconnecting when the "done" event is received.
 *  - Stops reconnecting when `enabled` becomes false or `jobId` becomes null.
 *  - Does NOT lose data – on reconnect the server re-sends all ready slides;
 *    the consumer is responsible for deduplication (e.g. by slide_index).
 *
 * Uses \n\n boundary scanning instead of per-line splitting so that SSE
 * events with large payloads (e.g. slide_ready with audio_base64) are
 * parsed correctly even when fragmented across ReadableStream chunks.
 */
export function useJobSse(
  jobId: string | null,
  enabled: boolean,
  callbacks: UseJobSseCallbacks,
): ConnectionState {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");

  // Keep the latest callbacks in a ref so the effect doesn't have to
  // restart when the user passes new anonymous functions.
  const cbRef = useRef(callbacks);
  cbRef.current = callbacks;

  useEffect(() => {
    if (!jobId || !enabled) {
      setConnectionState("disconnected");
      return;
    }

    const url = buildApiEndpoint(`/api/v1/jobs/${jobId}/events`);
    let cancelled = false;
    let retries = 0;

    async function run(): Promise<void> {
      while (!cancelled) {
        setConnectionState("connecting");
        console.log("[SSE] connecting to", url, "retry=", retries);

        try {
          const response = await fetch(url, {
            headers: { Accept: "text/event-stream" },
          });

          if (!response.ok) {
            console.log(
              "[SSE] connection failed:",
              response.status,
              response.statusText,
            );
            // 404 means the job doesn't exist — don't retry.
            if (response.status === 404) {
              setConnectionState("disconnected");
              return;
            }
            throw new Error(`HTTP ${response.status}`);
          }

          console.log("[SSE] connected successfully");
          setConnectionState("connected");
          retries = 0; // reset back-off on successful connection

          const reader = response.body!.getReader();
          const decoder = new TextDecoder();
          let buf = "";

          while (!cancelled) {
            const { done, value } = await reader.read();
            if (done) break;

            buf += decoder.decode(value, { stream: true });

            // Process complete SSE events: each is delimited by \n\n.
            // Uses indexOf-based boundary detection instead of line splitting
            // to avoid event-type loss when data: lines are fragmented across
            // ReadableStream chunks (common with large audio_base64 payloads).
            let idx: number;
            while ((idx = buf.indexOf("\n\n")) !== -1) {
              const rawEvent = buf.slice(0, idx);
              buf = buf.slice(idx + 2);

              const lines = rawEvent.split("\n");
              let evt = "";
              let data = "";

              for (const line of lines) {
                if (line.startsWith("event: ")) {
                  evt = line.slice(7).trim();
                } else if (line.startsWith("data: ")) {
                  data = line.slice(6);
                }
              }

              if (data) {
                switch (evt) {
                  case "status":
                    cbRef.current.onStatus(data);
                    break;
                  case "slide_ready":
                    cbRef.current.onSlideReady(data);
                    break;
                  case "done":
                    cbRef.current.onDone(data);
                    setConnectionState("disconnected");
                    return; // exit the loop + the whole `run` function
                  default:
                    console.warn("[SSE] unknown event type:", evt);
                }
              }
            }
          }

          // Stream ended without a "done" event – treat as unexpected.
          setConnectionState("disconnected");
          return;
        } catch (err) {
          if (cancelled) return;
          console.log(
            "[SSE] connection error, will retry:",
            err instanceof Error ? err.message : String(err),
          );

          // Exponential back-off: 1 s, 2 s, 4 s, 8 s, 16 s, 16 s, …
          retries += 1;
          const delay = Math.min(1000 * 2 ** (retries - 1), 16_000);
          console.log("[SSE] retrying in", delay, "ms (attempt", retries, ")");
          setConnectionState("disconnected");
          await new Promise((r) => setTimeout(r, delay));
        }
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [jobId, enabled]);

  return connectionState;
}
