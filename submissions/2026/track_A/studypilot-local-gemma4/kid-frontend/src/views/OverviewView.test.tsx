import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EveningResponse } from "../api/contracts";
import { SessionProvider } from "../state/session";
import { OverviewView } from "./OverviewView";

const SESSION_ID = "evening-capacity-ui";
const TASK_ID = "task-math-extra";
const CONFLICT_SESSION = {
  session_id: SESSION_ID,
  session_date: "2026-07-13",
  planning_date: "2026-07-13",
  version: 4,
  stage: "capacity_conflict",
  allowed_actions: ["adjust_capacity"],
  trace_id: "trace-capacity-ui",
  data: {
    narration: null,
    intake_draft: null,
    coverage_mode: "child_reported",
    inventory: [
      {
        id: TASK_ID,
        title: "数学拓展练习",
        subject: "数学",
        task_type: "书面",
        completion_state: "pending",
        estimated_minutes: 30,
        conservative_minutes: 160,
        priority: 3,
        must_do_tonight: true,
        due_at: "2026-07-14T08:00:00+08:00",
        child_estimate_minutes: 30,
        estimate_source: "child_adjusted",
        estimate_confidence: "low",
        notes: null,
        assignment_id: "assignment-math-extra",
        deadline_text: "明早检查",
        remaining_percent: 100,
        planning_bucket: "tonight_required",
        planned_evening_date: null,
        estimate_breakdown: [
          {
            component: "written_questions",
            label: "剩余数学题",
            task_type: "written",
            remaining_quantity: 6,
            unit: "题",
            reference_minutes: 10,
            calibrated_minutes: 15,
            source: "parent_range",
            confidence: "low",
          },
        ],
        estimate_signature: "written_questions",
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
        due_at: "2026-07-20T08:00:00+08:00",
        child_estimate_minutes: null,
        estimate_source: "domain_default",
        estimate_confidence: "low",
        notes: null,
        assignment_id: "assignment-history",
        deadline_text: "下周一提交",
        remaining_percent: 50,
        planning_bucket: "future_scheduled",
        planned_evening_date: "2026-07-18",
      },
      {
        id: "task-english-advance",
        title: "提前背诵英语课文",
        subject: "english",
        task_type: "recitation",
        completion_state: "pending",
        estimated_minutes: 15,
        conservative_minutes: 15,
        priority: 4,
        must_do_tonight: false,
        due_at: "2026-07-16T08:00:00+08:00",
        child_estimate_minutes: 15,
        estimate_source: "child_adjusted",
        estimate_confidence: "medium",
        notes: null,
        assignment_id: "assignment-english-advance",
        deadline_text: "周四提交",
        remaining_percent: 100,
        planning_bucket: "tonight_advance",
        planned_evening_date: null,
      },
      {
        id: "task-completed-legacy",
        title: "已完成的旧任务",
        subject: "chinese",
        task_type: "reading",
        completion_state: "completed",
        estimated_minutes: 0,
        conservative_minutes: 0,
        priority: 1,
        must_do_tonight: true,
        due_at: "2026-07-14T08:00:00+08:00",
        child_estimate_minutes: null,
        estimate_source: "domain_default",
        estimate_confidence: "high",
        notes: null,
        assignment_id: "assignment-completed-legacy",
        deadline_text: "明早检查",
        remaining_percent: 0,
        planning_bucket: "tonight_required",
        planned_evening_date: null,
        estimate_breakdown: [],
        estimate_signature: "reading_pages",
      },
    ],
    plan: {
      id: "plan-conflict",
      plan_version: 1,
      capacity: {
        available_minutes: 170,
        fixed_minutes: 0,
        task_minutes: 160,
        buffer_minutes: 25,
        required_minutes: 185,
        remaining_minutes: 0,
        shortfall_minutes: 15,
        feasible: false,
      },
      baseline_capacity: {
        available_minutes: 170,
        fixed_minutes: 0,
        task_minutes: 160,
        buffer_minutes: 25,
        required_minutes: 185,
        remaining_minutes: 0,
        shortfall_minutes: 15,
        feasible: false,
      },
      blocks: [],
      ordered_task_ids: [TASK_ID],
      deferred_task_ids: ["task-history-future", "task-english-advance"],
      future_scheduled_task_ids: ["task-history-future"],
      deadline_risk_task_ids: [],
      capacity_recovery: {
        mode: "start_earlier",
        baseline_shortfall_minutes: 15,
        earliest_start_time: "18:45:00",
        recommended_start_time: "19:15:00",
        speedup_percent: 0,
        pace_targets: [],
        recovered_minutes: 15,
        residual_shortfall_minutes: 0,
      },
      pace_targets: [],
      reason: "initial",
      committed: false,
      scheduled_optional_minutes: 0,
      true_surplus_minutes: 0,
      predicted_finish_at: null,
    },
    outcomes: [],
    time_boundary: {
      start_time: "19:30:00",
      sleep_time: "22:20:00",
      gross_minutes: 170,
      fixed_minutes: 0,
      net_minutes: 170,
    },
    future_assignments: [],
  },
} as EveningResponse;

describe("capacity conflict workspace", () => {
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
    queryClient.setQueryData(["evening", "today"], CONFLICT_SESSION);
    fetchMock.mockImplementation(async (_url: string, init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => init?.method === "PUT"
        ? {
            ...CONFLICT_SESSION,
            version: 5,
            stage: "inventory_confirmed",
            data: {
              ...CONFLICT_SESSION.data,
              plan: null,
              time_boundary: {
                ...CONFLICT_SESSION.data.time_boundary,
                start_time: "19:15:00",
                gross_minutes: 185,
                net_minutes: 185,
              },
            },
          }
        : { ...CONFLICT_SESSION, version: 6, stage: "plan_draft", allowed_actions: ["commit_plan"] },
    }));
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SessionProvider><OverviewView /></SessionProvider>
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

  it("applies the exact earlier start without deferring tomorrow work", async () => {
    expect(container.textContent).toContain("还差 15 分钟");
    expect(container.textContent).toContain("数学拓展练习");
    expect(container.textContent).toContain("后续已安排");
    expect(container.textContent).toContain("历史时间轴");
    expect(container.textContent).toContain("2026-07-18");
    expect(container.textContent).toContain("学习窗口");
    expect(container.textContent).toContain("固定事项");
    expect(container.textContent).toContain("净可安排");
    expect(container.textContent).toContain("保守任务用时");
    expect(container.textContent).toContain("总时间窗口");
    expect(container.textContent).toContain("更新时间边界");
    expect(container.textContent).toContain("今晚学习结束");
    expect(container.textContent).toContain("22:30睡眠不变");
    expect(container.textContent).not.toContain("建议延期");
    expect(container.textContent).not.toContain("保护睡觉时间");
    expect(container.textContent).toContain("有余力可提前");
    expect(container.textContent).not.toContain("可选任务");
    expect(container.textContent).not.toContain("请和家长");
    expect(container.textContent).toContain("估时依据");
    expect(container.textContent).toContain("剩余数学题");
    expect(container.textContent).toContain("10 → 15 分钟");
    expect(container.querySelector(".overview-task-grid")).not.toBeNull();
    expect(container.querySelector(".task-subject-mark")).not.toBeNull();
    const mustSection = container.querySelector("section[aria-labelledby='must-title']");
    const completedSection = container.querySelector("section[aria-labelledby='complete-title']");
    expect(mustSection?.textContent).not.toContain("已完成的旧任务");
    expect(completedSection?.textContent).toContain("已完成的旧任务");

    const acceptButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("采用这个开始时间"),
    );
    expect(acceptButton).toBeDefined();
    await act(async () => acceptButton?.click());

    const timeRequest = fetchMock.mock.calls.find((call) => call[1]?.method === "PUT")?.[1] as RequestInit;
    expect(JSON.parse(String(timeRequest.body))).toMatchObject({
      start_time: "19:15:00",
      sleep_time: "22:20:00",
      expected_version: 4,
    });
    const planRequest = fetchMock.mock.calls.find((call) => call[1]?.method === "POST")?.[1] as RequestInit;
    expect(JSON.parse(String(planRequest.body))).toMatchObject({
      expected_version: 5,
      reason: "initial",
    });
    expect(JSON.parse(String(planRequest.body))).not.toHaveProperty("deadline_risk_task_ids");
  });
});
