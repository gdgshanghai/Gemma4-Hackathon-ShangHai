import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EveningResponse } from "../api/contracts";
import { SessionProvider, useSession } from "./session";

const CLOSED_SESSION: EveningResponse = {
  session_id: "evening-closed-test",
  session_date: "2026-07-13",
  planning_date: "2026-07-13",
  version: 7,
  stage: "closed",
  allowed_actions: [],
  trace_id: "trace-test",
  data: {
    narration: null,
    intake_draft: null,
    coverage_mode: "child_reported",
    inventory: [],
    plan: null,
    outcomes: [],
    time_boundary: {
      start_time: "19:30:00",
      sleep_time: "22:30:00",
      gross_minutes: 180,
      fixed_minutes: 0,
      net_minutes: 180,
    },
    future_assignments: [],
  },
};

describe("SessionProvider daily restore", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;
  let latestContext: ReturnType<typeof useSession> | undefined;
  const fetchMock = vi.fn();

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    localStorage.clear();
    localStorage.setItem("studypilot.lastSessionId", "stale-session-id");
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => CLOSED_SESSION,
    });
    vi.stubGlobal("fetch", fetchMock);

    function Probe() {
      latestContext = useSession();
      return null;
    }

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SessionProvider><Probe /></SessionProvider>
        </QueryClientProvider>,
      );
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    queryClient.clear();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  function context() {
    if (!latestContext) throw new Error("session context was not rendered");
    return latestContext;
  }

  it("restores the server's current evening and ignores a stale local pointer", async () => {
    await act(async () => {
      await vi.waitFor(() => expect(context().session).toEqual(CLOSED_SESSION));
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8040/api/v1/evenings/today",
      expect.any(Object),
    );
    expect(queryClient.getQueryData(["evening", "today"])).toEqual(CLOSED_SESSION);
    expect(context()).not.toHaveProperty("startNewEvening");
  });
});
