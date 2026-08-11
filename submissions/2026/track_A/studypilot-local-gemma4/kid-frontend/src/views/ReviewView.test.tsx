import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EveningResponse } from "../api/contracts";
import { SessionProvider } from "../state/session";
import { ReviewView } from "./ReviewView";

const SESSION_ID = "evening-review-ui";
const TASK_ID = "task-review-math";
const COMMITTED_SESSION = {
  session_id: SESSION_ID,
  session_date: "2026-07-13",
  planning_date: "2026-07-13",
  version: 6,
  stage: "committed",
  allowed_actions: ["close_evening"],
  trace_id: "trace-review-ui",
  data: {
    narration: null,
    intake_draft: null,
    coverage_mode: "child_reported",
    inventory: [
      {
        id: TASK_ID,
        title: "数学练习册",
        subject: "数学",
        task_type: "书面",
        completion_state: "pending",
        estimated_minutes: 30,
        conservative_minutes: 35,
        priority: 1,
        must_do_tonight: true,
        due_at: "2026-07-14T08:00:00+08:00",
        child_estimate_minutes: 30,
        estimate_source: "child_adjusted",
        estimate_confidence: "low",
        notes: null,
        assignment_id: "assignment-review-math",
        deadline_text: "明早检查",
        remaining_percent: 100,
        planning_bucket: "tonight_required",
        planned_evening_date: null,
      },
    ],
    plan: {
      id: "plan-review",
      plan_version: 1,
      capacity: {
        available_minutes: 110,
        fixed_minutes: 0,
        task_minutes: 35,
        buffer_minutes: 15,
        required_minutes: 50,
        remaining_minutes: 60,
        shortfall_minutes: 0,
        feasible: true,
      },
      baseline_capacity: {
        available_minutes: 110,
        fixed_minutes: 0,
        task_minutes: 35,
        buffer_minutes: 15,
        required_minutes: 50,
        remaining_minutes: 60,
        shortfall_minutes: 0,
        feasible: true,
      },
      blocks: [],
      ordered_task_ids: [TASK_ID],
      deferred_task_ids: [],
      future_scheduled_task_ids: [],
      deadline_risk_task_ids: [],
      capacity_recovery: null,
      pace_targets: [],
      reason: "initial",
      committed: true,
      scheduled_optional_minutes: 0,
      true_surplus_minutes: 60,
      predicted_finish_at: "2026-07-12T20:30:00+08:00",
    },
    outcomes: [],
    time_boundary: {
      start_time: "20:30:00",
      sleep_time: "22:20:00",
      gross_minutes: 110,
      fixed_minutes: 0,
      net_minutes: 110,
    },
    future_assignments: [],
  },
} as EveningResponse;

describe("minimal bedtime review", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;
  const fetchMock = vi.fn();

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    localStorage.clear();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    fetchMock.mockImplementation(async (_url: string, init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => init?.method === "POST"
        ? {
            ...COMMITTED_SESSION,
            planning_date: "2026-10-12",
            version: 7,
            stage: "closed",
            allowed_actions: [],
          }
        : COMMITTED_SESSION,
    }));
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SessionProvider><ReviewView /></SessionProvider>
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

  it("submits one optional largest deviation with actual minutes", async () => {
    await act(async () => {
      await vi.waitFor(() => {
        expect(container.querySelector("select[name='deviation-task']")).not.toBeNull();
      });
    });
    expect(container.querySelector("section[aria-label='未完成例外']")).not.toBeNull();
    expect(container.textContent).toContain("没有勾选未完成项：全部完成");
    const taskSelect = container.querySelector<HTMLSelectElement>("select[name='deviation-task']");
    expect(taskSelect).not.toBeNull();
    await act(async () => {
      if (!taskSelect) return;
      taskSelect.value = TASK_ID;
      taskSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const minutes = container.querySelector<HTMLInputElement>("input[name='actual-minutes']");
    expect(minutes).not.toBeNull();
    await act(async () => {
      if (!minutes) return;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(minutes, "47");
      minutes.dispatchEvent(new Event("input", { bubbles: true }));
      minutes.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const saveButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("保存睡前复盘"),
    );
    await act(async () => saveButton?.click());

    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST")?.[1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      expected_version: 6,
      unfinished_task_ids: [],
      largest_deviation: { task_id: TASK_ID, actual_minutes: 47 },
    });
    expect(container.textContent).toContain("2026-10-12 · 已归档");
    expect(container.textContent).not.toContain("2026-07-13 · 已归档");
    expect(container.querySelectorAll("button")).toHaveLength(0);
  });

  it("only asks the child to mark unfinished exceptions", async () => {
    const checkbox = await vi.waitFor(() => {
      const input = container.querySelector<HTMLInputElement>("input[type='checkbox']");
      expect(input).not.toBeNull();
      return input;
    });
    expect(checkbox).not.toBeNull();
    expect(container.textContent).toContain("没有勾选未完成项：全部完成");

    await act(async () => checkbox?.click());

    expect(container.textContent).toContain("已选 1 项未完成");
    expect(container.textContent).toContain("数学练习册");
  });
});
