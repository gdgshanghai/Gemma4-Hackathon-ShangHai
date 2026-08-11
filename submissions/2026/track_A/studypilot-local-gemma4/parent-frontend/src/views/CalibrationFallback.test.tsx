import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { currentWeekStart } from "../date";
import { CalibrationView } from "./CalibrationView";

const SCENARIO = {
  scenario_id: "grade7-busy-thursday-v1",
  label: "初一开学第六周 · 多科忙碌周四",
  planning_date: "2026-10-15",
  start_time: "19:30:00",
  sleep_time: "22:30:00",
  school_brief_text: "模拟学校作业单",
  child_report_text: "模拟孩子陈述",
  weekly_calibration_text: "模拟家长观察",
  weekly_calibration_groups: [
    { subject: "mathematics", task_type: "written", conservative_minutes: 30 },
    { subject: "chinese", task_type: "reading", conservative_minutes: 20 },
    { subject: "english", task_type: "recitation", conservative_minutes: 15 },
    { subject: "geography", task_type: "map_reading", conservative_minutes: 15 },
  ],
};

const RECOVERY = {
  calibration_id: "calibration-1",
  calibration_version: 2,
  profile_version: 0,
  stage: "model_unavailable",
  allowed_actions: [
    "retry_last_turn",
    "use_simplified_calibration",
    "abandon_profile_patch",
  ],
  trace_id: "trace-recovery",
  data: {
    kind: "calibration_recovery",
    input_saved: true,
    input_receipt_id: "receipt-1",
    resume_stage: "profile_propose",
    pending_kind: "model_retry",
    pending_entity_id: "checkpoint-1",
    failure_code: "tool_schema_repair_exhausted",
  },
  delivery: { replayed: false },
};

const PROPOSAL = {
  calibration_id: "calibration-1",
  calibration_version: 3,
  profile_version: 0,
  stage: "needs_confirmation",
  allowed_actions: ["commit_profile_patch", "revise_profile_patch", "abandon_profile_patch"],
  trace_id: "trace-proposal",
  data: {
    kind: "profile_patch_proposal",
    draft: {
      id: "draft-1",
      calibration_id: "calibration-1",
      receipt_id: "receipt-1",
      base_profile_version: 0,
      proposal_digest: "a".repeat(64),
      draft_digest: "b".repeat(64),
      observations: [
        {
          action: "assert",
          category: "task_speed",
          subject: "mathematics",
          task_type: "written",
          metric: "estimated_actual_ratio",
          value_text: null,
          value_number: 1.7,
          unit: "ratio",
          confidence: 0.7,
          sample_count: 3,
          observed_at: "2026-07-16T15:49:09+08:00",
          target_event_id: null,
          operation_id: "operation-1",
        },
      ],
      revises_draft_id: null,
      created_at: "2026-07-16T15:49:09+08:00",
    },
    diff_preview: [],
    narration: null,
    narration_status: "not_requested",
    unapplied_notes: ["英语开始前需要提醒一次"],
    calibration_details: [
      {
        subject: "mathematics",
        task_type: "written",
        workload_band: "medium",
        reference_minutes: 20,
        observed_p80_minutes: 34,
        sample_count: 3,
        suggested_ratio: 1.7,
      },
    ],
  },
  delivery: { replayed: false },
};

function noData() {
  return { value: null, numerator: 0, denominator: 0, status: "no_data" };
}

describe("parent calibration fallback", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (input.includes("/demo/scenario")) {
        return { ok: true, status: 200, json: async () => SCENARIO };
      }
      if (input.includes("/parent/weekly-summary")) {
        const weekStart = currentWeekStart();
        return {
          ok: true,
          status: 200,
          json: async () => ({
            trace_id: "trace-weekly",
            data: {
              week_start: weekStart,
              week_end: weekStart,
              profile_version: 0,
              latest_calibration: {
                calibration_id: "calibration-1",
                calibration_version: 2,
                profile_version: 0,
                state: "model_unavailable",
                occurred_at: "2026-07-16T15:49:09+08:00",
              },
              confirmed_observation_count: 0,
              estimate_error: noData(),
              omissions: noData(),
              start_confidence: noData(),
              parent_interventions: noData(),
            },
          }),
        };
      }
      if (input.endsWith("/parent/calibrations/calibration-1") && !init?.method) {
        return { ok: true, status: 200, json: async () => RECOVERY };
      }
      if (input.endsWith("/parent/calibrations/calibration-1/simplify") && init?.method === "POST") {
        return { ok: true, status: 200, json: async () => PROPOSAL };
      }
      throw new Error(`unexpected request: ${input}`);
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    queryClient.clear();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  async function renderView() {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <CalibrationView />
        </QueryClientProvider>,
      );
    });
    await vi.waitFor(() => expect(container.textContent).toContain("模型输出未通过格式校验"));
  }

  it("shows bounded recovery actions and explains that planning parameters did not change", async () => {
    await renderView();

    expect(container.querySelector("section[aria-label='校准恢复']")).not.toBeNull();
    expect(container.textContent).toContain("原始观察已保存，规划参数没有改变");
    expect(container.textContent).toContain("重试一次");
    expect(container.textContent).toContain("使用简化校准");
    expect(container.textContent).toContain("本周暂不更新");
  });

  it("fills the demo fallback rows without posting, then submits one simplify request", async () => {
    await renderView();
    const fallbackButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("使用简化校准"),
    );
    await act(async () => fallbackButton?.click());

    const presetButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("载入演示预设"),
    );
    await act(async () => presetButton?.click());

    const minuteInputs = [...container.querySelectorAll<HTMLInputElement>('input[type="number"]')];
    expect(minuteInputs.map((input) => input.value)).toEqual(["30", "20", "15", "15"]);
    expect(container.textContent).toContain("模拟数据，尚未保存");
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(0);

    const submitButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("生成待确认建议"),
    );
    await act(async () => submitButton?.click());
    await vi.waitFor(() => expect(container.textContent).toContain("英语开始前需要提醒一次"));

    const simplifyCalls = fetchMock.mock.calls.filter((call) =>
      String(call[0]).endsWith("/parent/calibrations/calibration-1/simplify"),
    );
    expect(simplifyCalls).toHaveLength(1);
    const simplifyCall = simplifyCalls[0]!;
    expect(JSON.parse(simplifyCall[1]?.body as string)).toEqual({
      expected_calibration_version: 2,
      duration_groups: SCENARIO.weekly_calibration_groups,
    });
    expect(container.textContent).toContain("数学");
    expect(container.textContent).toContain("书面作业");
    expect(container.textContent).toContain("参考 20 分钟");
    expect(container.textContent).toContain("观察 P80 34 分钟");
    expect(container.textContent).toContain("3 个样本");
    expect(container.textContent).toContain("建议 1.70 倍");
    expect(container.querySelector("section[aria-label='校准证据']")).not.toBeNull();
  });
});
