import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { EveningResponse } from "../api/contracts";
import { SessionProvider } from "../state/session";
import { RouteView } from "./RouteView";


const SESSION = {
  session_id: "evening-focus-route",
  session_date: "2026-10-12",
  planning_date: "2026-10-12",
  version: 5,
  stage: "plan_draft",
  allowed_actions: ["commit_plan"],
  trace_id: "trace-focus-route",
  data: {
    narration: null,
    intake_draft: null,
    coverage_mode: "school_verified",
    inventory: [
      {
        id: "task-english",
        title: "英语词汇与背诵",
        subject: "english",
        task_type: "recitation",
        completion_state: "pending",
        estimated_minutes: 10,
        conservative_minutes: 10,
        priority: 0,
        must_do_tonight: true,
        due_at: "2026-10-13T08:00:00+08:00",
        child_estimate_minutes: null,
        estimate_source: "domain_default",
        estimate_confidence: "low",
        notes: null,
        assignment_id: "assignment-english",
        deadline_text: "明早检查",
        remaining_percent: 100,
        planning_bucket: "tonight_required",
        planned_evening_date: null,
        estimate_breakdown: [],
        estimate_signature: null,
      },
      {
        id: "task-history-future",
        title: "历史时间轴",
        subject: "history",
        task_type: "written",
        completion_state: "partial",
        estimated_minutes: 10,
        conservative_minutes: 10,
        priority: 4,
        must_do_tonight: false,
        due_at: "2026-10-16T08:00:00+08:00",
        child_estimate_minutes: null,
        estimate_source: "domain_default",
        estimate_confidence: "low",
        notes: null,
        assignment_id: "assignment-history-future",
        deadline_text: "周五提交",
        remaining_percent: 50,
        planning_bucket: "future_scheduled",
        planned_evening_date: "2026-10-14",
        estimate_breakdown: [],
        estimate_signature: null,
      },
    ],
    plan: {
      id: "plan-focus",
      plan_version: 2,
      capacity: {
        available_minutes: 23,
        fixed_minutes: 0,
        task_minutes: 8,
        buffer_minutes: 15,
        required_minutes: 23,
        remaining_minutes: 0,
        shortfall_minutes: 0,
        feasible: true,
      },
      baseline_capacity: {
        available_minutes: 23,
        fixed_minutes: 0,
        task_minutes: 10,
        buffer_minutes: 15,
        required_minutes: 25,
        remaining_minutes: 0,
        shortfall_minutes: 2,
        feasible: false,
      },
      blocks: [{
        id: "block-task",
        block_type: "task",
        label: "英语词汇与背诵",
        starts_at: "2026-10-12T21:57:00+08:00",
        ends_at: "2026-10-12T22:05:00+08:00",
        ordinal: 0,
        task_id: "task-english",
      }],
      ordered_task_ids: ["task-english"],
      deferred_task_ids: [],
      future_scheduled_task_ids: [],
      deadline_risk_task_ids: [],
      capacity_recovery: {
        mode: "focus_pace",
        baseline_shortfall_minutes: 2,
        earliest_start_time: "18:45:00",
        recommended_start_time: "18:45:00",
        speedup_percent: 20,
        pace_targets: [{ task_id: "task-english", conservative_minutes: 10, target_minutes: 8 }],
        recovered_minutes: 2,
        residual_shortfall_minutes: 0,
      },
      pace_targets: [{ task_id: "task-english", conservative_minutes: 10, target_minutes: 8 }],
      reason: "focus_pace",
      committed: false,
      scheduled_optional_minutes: 0,
      true_surplus_minutes: 0,
      predicted_finish_at: "2026-10-12T22:20:00+08:00",
    },
    outcomes: [],
    time_boundary: {
      start_time: "21:57:00",
      sleep_time: "22:20:00",
      gross_minutes: 23,
      fixed_minutes: 0,
      net_minutes: 23,
    },
    future_assignments: [],
  },
} as EveningResponse;

describe("focus route", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;

  beforeEach(async () => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
    queryClient.setQueryData(["evening", "today"], SESSION);
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SessionProvider><RouteView onOpenReview={() => undefined} /></SessionProvider>
        </QueryClientProvider>,
      );
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    queryClient.clear();
    container.remove();
  });

  it("keeps the conservative estimate visible beside tonight's target", () => {
    expect(container.querySelector("section.route-command[aria-label='计划结果']")).not.toBeNull();
    expect(container.textContent).toContain("预计结束");
    expect(container.textContent).toContain("第一步");
    expect(container.textContent).toContain("英语词汇与背诵");
    expect(container.textContent).toContain("预留缓冲");
    expect(container.textContent).toContain("真实余量");
    expect(container.textContent).toContain("保守 10 分钟");
    expect(container.textContent).toContain("今晚目标 8 分钟");
    expect(container.textContent).toContain("专注目标不改写家庭基线");
    expect(container.textContent).toContain("后续已安排");
    expect(container.textContent).toContain("历史时间轴");
    expect(container.querySelector(".timeline-row-layout")).not.toBeNull();
    expect(container.querySelector(".timeline-duration")?.textContent?.trim()).toBe("8 分钟");
  });
});
