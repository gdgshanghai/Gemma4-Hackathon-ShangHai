import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { currentWeekStart } from "../date";
import { BriefView } from "./BriefView";
import { CalibrationView } from "./CalibrationView";

const SCENARIO = {
  scenario_id: "grade7-busy-thursday-v1",
  label: "初一开学第六周 · 多科忙碌周四",
  planning_date: "2026-10-15",
  start_time: "19:30:00",
  sleep_time: "22:30:00",
  school_brief_text: "【模拟作业单】\n地理（明早检查）：完成经纬网练习8题。",
  child_report_text: "演示孩子陈述。",
  weekly_calibration_text: "本周可核对观察：数学三次用时31、34、29分钟。",
  weekly_calibration_groups: [
    { subject: "mathematics", task_type: "written", conservative_minutes: 30 },
    { subject: "chinese", task_type: "reading", conservative_minutes: 20 },
    { subject: "english", task_type: "recitation", conservative_minutes: 15 },
    { subject: "geography", task_type: "map_reading", conservative_minutes: 15 },
  ],
};
const NOT_FOUND = {
  error: { code: "not_found", message: "Not found.", issues: [] },
  trace_id: "trace-not-found",
  recovery: null,
};

function noData() {
  return { value: null, numerator: 0, denominator: 0, status: "no_data" };
}

describe("parent demo presets", () => {
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
      if (input.includes("/school-briefs?") && !init?.method) {
        return { ok: false, status: 404, json: async () => NOT_FOUND };
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
              week_end: new Date(`${weekStart}T12:00:00`).toISOString().slice(0, 10),
              profile_version: 0,
              latest_calibration: null,
              confirmed_observation_count: 0,
              estimate_error: noData(),
              omissions: noData(),
              start_confidence: noData(),
              parent_interventions: noData(),
            },
          }),
        };
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

  async function render(view: React.ReactNode) {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>{view}</QueryClientProvider>,
      );
    });
  }

  it("fills the school brief without saving", async () => {
    await render(<BriefView />);
    expect(container.querySelector("section[aria-label='学校原文']")).not.toBeNull();
    expect(container.querySelector("aside[aria-label='当前状态']")).not.toBeNull();
    const button = await vi.waitFor(() => {
      const candidate = [...container.querySelectorAll("button")].find((item) =>
        item.textContent?.includes("载入示例作业单"),
      );
      expect(candidate).toBeDefined();
      return candidate!;
    });
    await act(async () => button.click());
    expect(container.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe(SCENARIO.school_brief_text);
    expect(container.textContent).toContain("模拟数据，尚未保存");
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(0);
  });

  it("keeps the brief page usable while a date input is temporarily empty", async () => {
    await render(<BriefView />);
    const dateInput = container.querySelector<HTMLInputElement>("input[type='date']");
    expect(dateInput).not.toBeNull();

    await act(async () => {
      if (!dateInput) return;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(dateInput, "");
      dateInput.dispatchEvent(new Event("input", { bubbles: true }));
      dateInput.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(container.textContent).toContain("请选择日期");
    expect(container.querySelector("main")).not.toBeNull();
    expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith("brief_date="))).toBe(false);
  });

  it("fills weekly calibration without calling the model", async () => {
    await render(<CalibrationView />);
    const button = await vi.waitFor(() => {
      const candidate = [...container.querySelectorAll("button")].find((item) =>
        item.textContent?.includes("载入示例观察"),
      );
      expect(candidate).toBeDefined();
      return candidate!;
    });
    expect(container.querySelector("section[aria-label='本周校准观察']")).not.toBeNull();
    await act(async () => button.click());
    expect(container.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe(
      SCENARIO.weekly_calibration_text,
    );
    expect(container.textContent).toContain("模拟数据，尚未保存");
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(0);
  });
});
