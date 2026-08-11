import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "../state/session";
import { IntakeView } from "./IntakeView";

const CHILD_REPORT = "演示孩子陈述，故意没有地理。";
const SCENARIO = {
  scenario_id: "grade7-busy-monday-v2",
  label: "初一开学第六周 · 多科忙碌周一",
  planning_date: "2026-10-12",
  start_time: "19:30:00",
  sleep_time: "22:20:00",
  school_brief_text: "地理（明早检查）：完成经纬网练习8题。",
  child_report_text: CHILD_REPORT,
  weekly_calibration_text: "数学三次用时28、30、29分钟。",
  weekly_calibration_groups: [
    { subject: "mathematics", task_type: "written", conservative_minutes: 30 },
    { subject: "chinese", task_type: "reading", conservative_minutes: 20 },
    { subject: "english", task_type: "recitation", conservative_minutes: 15 },
    { subject: "geography", task_type: "map_reading", conservative_minutes: 15 },
  ],
};
const CREATED = {
  session_id: "demo-created-session",
  session_date: "2026-07-16",
  planning_date: "2026-10-12",
  version: 1,
  stage: "created",
  allowed_actions: ["describe_homework"],
  trace_id: "trace-demo-create",
  data: {
    narration: null,
    intake_draft: null,
    coverage_mode: null,
    inventory: [],
    plan: null,
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
};
const NOT_FOUND = {
  error: { code: "not_found", message: "Not found.", issues: [] },
  trace_id: "trace-not-found",
  recovery: null,
};

function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("kid demo preset", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;
  const fetchMock = vi.fn();

  beforeEach(async () => {
    vi.stubEnv("VITE_DEMO_MODE", "true");
    fetchMock.mockClear();
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    fetchMock.mockImplementation(async (input: string, init?: RequestInit) => {
      if (input.endsWith("/api/v1/evenings/today")) {
        return { ok: false, status: 404, json: async () => NOT_FOUND };
      }
      if (input.endsWith("/api/v1/demo/scenario")) {
        return { ok: true, status: 200, json: async () => SCENARIO };
      }
      if (input.endsWith("/api/v1/demo/evenings/today/reset") && init?.method === "POST") {
        return { ok: true, status: 200, json: async () => CREATED };
      }
      throw new Error(`unexpected request: ${input}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SessionProvider><IntakeView /></SessionProvider>
        </QueryClientProvider>,
      );
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    queryClient.clear();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("fills the complete scenario without submitting it", async () => {
    const presetButton = await vi.waitFor(() => {
      const button = [...container.querySelectorAll("button")].find((item) =>
        item.textContent?.includes("载入演示情景"),
      );
      expect(button).toBeDefined();
      return button!;
    });
    await act(async () => presetButton.click());

    expect(container.textContent).toContain("模拟日期：2026-10-12 星期一");
    const timeInputs = container.querySelectorAll<HTMLInputElement>('input[type="time"]');
    expect(timeInputs[0]?.value).toBe("19:30");
    expect(timeInputs[1]?.value).toBe("22:20");
    expect(timeInputs[0]?.min).toBe("18:45");
    expect(timeInputs[1]?.max).toBe("22:20");
    expect(container.textContent).toContain("170 分钟");
    expect(container.textContent).toContain("今晚学习结束");
    expect(container.textContent).toContain("结束后留给睡前准备");
    expect(container.textContent).toContain("22:30按时睡觉");
    expect(container.textContent).not.toContain("计划几点睡觉");
    expect(container.querySelector('input[type="number"]')).toBeNull();
    expect(container.textContent).toContain("模拟数据，尚未保存");
    expect(container.querySelector("aside[aria-label='今晚已知边界']")).not.toBeNull();
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(0);

    const startButton = [...container.querySelectorAll("button")].find((item) =>
      item.textContent?.includes("开始今晚盘点"),
    );
    await act(async () => startButton?.click());
    await vi.waitFor(() => {
      expect(container.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe(CHILD_REPORT);
    });
    const postCalls = fetchMock.mock.calls.filter((call) => call[1]?.method === "POST");
    expect(postCalls).toHaveLength(1);
    expect(postCalls[0]?.[0]).toMatch(/\/api\/v1\/demo\/evenings\/today\/reset$/);
    expect(JSON.parse(String(postCalls[0]?.[1]?.body))).toEqual({ expected_session_id: null });
    expect(
      fetchMock.mock.calls.some(
        (call) => call[0].endsWith("/api/v1/evenings") && call[1]?.method === "POST",
      ),
    ).toBe(false);
  });

  it("recalculates the maximum family window from 18:45", async () => {
    const presetButton = await vi.waitFor(() => {
      const button = [...container.querySelectorAll("button")].find((item) =>
        item.textContent?.includes("载入演示情景"),
      );
      expect(button).toBeDefined();
      return button!;
    });
    await act(async () => presetButton.click());

    const startInput = container.querySelectorAll<HTMLInputElement>('input[type="time"]')[0]!;
    await act(async () => {
      setInputValue(startInput, "18:45");
    });

    expect(startInput.value).toBe("18:45");
    expect(container.textContent).toContain("215 分钟");
  });

  it("fills the homework input when today's evening already exists", async () => {
    await act(async () => {
      queryClient.setQueryData(["evening", "today"], CREATED);
    });

    const presetButton = await vi.waitFor(() => {
      const button = [...container.querySelectorAll("button")].find((item) =>
        item.textContent?.includes("一键代入预设作业"),
      );
      expect(button).toBeDefined();
      return button!;
    });

    expect(container.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe("");
    await act(async () => presetButton.click());

    expect(container.querySelector<HTMLTextAreaElement>("textarea")?.value).toBe(CHILD_REPORT);
    expect(container.textContent).toContain("模拟数据，尚未保存");
    expect(container.querySelector("aside[aria-label='今晚已知边界']")).not.toBeNull();
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(0);
  });
});
