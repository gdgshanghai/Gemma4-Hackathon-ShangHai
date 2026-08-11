import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CapacityRecovery, InventoryTask } from "../api/contracts";
import { CapacityRecoveryPanel } from "./CapacityRecoveryPanel";


const TASK = {
  id: "task-english",
  title: "英语词汇与背诵",
  subject: "english",
  task_type: "recitation",
  completion_state: "pending",
  estimated_minutes: 10,
  conservative_minutes: 10,
  priority: 1,
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
} satisfies InventoryTask;

function recovery(
  mode: CapacityRecovery["mode"],
): CapacityRecovery {
  return {
    mode,
    baseline_shortfall_minutes: mode === "start_earlier" ? 15 : 30,
    earliest_start_time: "18:45:00",
    recommended_start_time: mode === "start_earlier" ? "19:15:00" : "18:45:00",
    speedup_percent: mode === "start_earlier" ? 0 : 20,
    pace_targets: mode === "start_earlier" ? [] : [{
      task_id: TASK.id,
      conservative_minutes: 10,
      target_minutes: 8,
    }],
    recovered_minutes: mode === "manual_choice" ? 20 : 30,
    residual_shortfall_minutes: mode === "manual_choice" ? 10 : 0,
  };
}

describe("capacity recovery panel", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("offers an exact earlier start without suggesting task deferral", async () => {
    const onStartEarlier = vi.fn();
    await act(async () => {
      root.render(
        <CapacityRecoveryPanel
          recovery={recovery("start_earlier")}
          tasks={[TASK]}
          pending={false}
          onStartEarlier={onStartEarlier}
          onAcceptFocus={() => undefined}
          onManualChoice={() => undefined}
        />,
      );
    });

    expect(container.textContent).toContain("还差 15 分钟");
    expect(container.textContent).toContain("今晚从 19:15 开始");
    expect(container.textContent).toContain("22:30睡眠不变");
    expect(container.textContent).not.toContain("建议延期");
    const button = container.querySelector("button");
    await act(async () => button?.click());
    expect(onStartEarlier).toHaveBeenCalledOnce();
  });

  it("shows conservative and bounded focus targets", async () => {
    const onAcceptFocus = vi.fn();
    await act(async () => {
      root.render(
        <CapacityRecoveryPanel
          recovery={recovery("focus_pace")}
          tasks={[TASK]}
          pending={false}
          onStartEarlier={() => undefined}
          onAcceptFocus={onAcceptFocus}
          onManualChoice={() => undefined}
        />,
      );
    });

    expect(container.textContent).toContain("最高不超过 20%");
    expect(container.textContent).toContain("保守 10 分钟");
    expect(container.textContent).toContain("今晚目标 8 分钟");
    const button = container.querySelector("button");
    await act(async () => button?.click());
    expect(onAcceptFocus).toHaveBeenCalledOnce();
  });

  it("leaves every deadline-risk task unselected until the child chooses", async () => {
    const onManualChoice = vi.fn();
    await act(async () => {
      root.render(
        <CapacityRecoveryPanel
          recovery={recovery("manual_choice")}
          tasks={[TASK]}
          pending={false}
          onStartEarlier={() => undefined}
          onAcceptFocus={() => undefined}
          onManualChoice={onManualChoice}
        />,
      );
    });

    const checkbox = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    const button = container.querySelector<HTMLButtonElement>("button")!;
    expect(checkbox.checked).toBe(false);
    expect(button.disabled).toBe(true);
    expect(container.textContent).toContain("已到系统规划极限");
    expect(container.textContent).toContain("明日截止风险");

    await act(async () => checkbox.click());
    expect(checkbox.checked).toBe(true);
    expect(button.disabled).toBe(false);
    await act(async () => button.click());
    expect(onManualChoice).toHaveBeenCalledWith([TASK.id]);
  });
});
