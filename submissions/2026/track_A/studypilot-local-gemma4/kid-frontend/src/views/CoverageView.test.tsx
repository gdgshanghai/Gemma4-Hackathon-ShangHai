import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SessionProvider } from "../state/session";
import { IntakeView } from "./IntakeView";
import { OverviewView } from "./OverviewView";

const SESSION_ID = "evening-school-coverage-test";
const DRAFT_SESSION = {
  session_id: SESSION_ID,
  session_date: "2026-07-13",
  planning_date: "2026-07-13",
  version: 2,
  stage: "intake_draft",
  allowed_actions: ["add_intake_turn", "confirm_inventory"],
  trace_id: "trace-draft",
  data: {
    narration: "请确认合并清单。",
    intake_draft: {
      id: "draft-school-coverage",
      coverage_notes: ["学校作业单中的英语背诵未在你的清单中提及。"],
      tasks: [
        {
          title: "英语背诵",
          subject: "english",
          completion_state: "pending",
          child_estimate_minutes: null,
          deadline_text: "明早检查",
          total_units: null,
          completed_units: null,
          notes: null,
        },
      ],
    },
    coverage_mode: null,
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

const CONFIRMED_SESSION = {
  ...DRAFT_SESSION,
  version: 3,
  stage: "inventory_confirmed",
  allowed_actions: ["build_plan"],
  trace_id: "trace-confirmed",
  data: {
    ...DRAFT_SESSION.data,
    coverage_mode: "school_verified",
    inventory: [],
  },
};

describe("school coverage views", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;
  let response: unknown = DRAFT_SESSION;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    localStorage.clear();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["evening", "today"], DRAFT_SESSION);
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => response,
    })));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    queryClient.clear();
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  async function render(view: React.ReactNode) {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <SessionProvider>{view}</SessionProvider>
        </QueryClientProvider>,
      );
    });
  }

  it("shows draft differences and verified copy only after confirmation", async () => {
    await render(<IntakeView />);

    expect(container.textContent).toContain(
      "学校作业单中的英语背诵未在你的清单中提及。",
    );
    expect(container.textContent).toContain("只补充遗漏或更正即可");
    expect(container.textContent).toContain("应用补充");
    expect(container.textContent).toContain("遗漏项目已经加入清单");
    expect(container.textContent).toContain("只需补充完成状态或剩余情况");
    expect(container.querySelector("aside[aria-label='今晚已知边界']")).not.toBeNull();

    response = CONFIRMED_SESSION;
    queryClient.setQueryData(["evening", "today"], CONFIRMED_SESSION);
    await render(<OverviewView />);

    expect(container.textContent).toContain("已对照学校作业单");
    expect(container.textContent).not.toContain("依据你提供的清单");
  });
});
