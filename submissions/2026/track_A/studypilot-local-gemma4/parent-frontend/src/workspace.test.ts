import { describe, expect, it } from "vitest";

import {
  calibrationFailureMessage,
  calibrationPresentation,
  canonicalParentPath,
  eveningRecordStatus,
} from "./workspace";
import { EveningResultSchema } from "./api/contracts";

describe("parent workspace state and routes", () => {
  it("accepts the child plan recovery fields as read-only evidence", () => {
    const planShape = EveningResultSchema.shape.data.shape.plan.unwrap().shape;

    expect(planShape).toHaveProperty("baseline_capacity");
    expect(planShape).toHaveProperty("capacity_recovery");
    expect(planShape).toHaveProperty("pace_targets");
    expect(planShape).toHaveProperty("deadline_risk_task_ids");
  });

  it("falls back unknown paths to the school brief tab", () => {
    expect(canonicalParentPath("/calibration")).toBe("/calibration");
    expect(canonicalParentPath("/result")).toBe("/result");
    expect(canonicalParentPath("/anything-else")).toBe("/brief");
  });

  it("labels evening records without adding a parent approval state", () => {
    expect(eveningRecordStatus("closed", "2026-07-13", "2026-07-13")).toBe("archived");
    expect(eveningRecordStatus("committed", "2026-07-12", "2026-07-13")).toBe("incomplete");
    expect(eveningRecordStatus("committed", "2026-07-13", "2026-07-13")).toBe("in_progress");
  });

  it.each([
    [undefined, "new", false],
    [
      { stage: "needs_confirmation", allowed_actions: ["commit_profile_patch"] },
      "review",
      false,
    ],
    [
      { stage: "model_unavailable", allowed_actions: ["retry_last_turn"] },
      "recovery",
      false,
    ],
    [
      { stage: "committed", allowed_actions: ["start_calibration"] },
      "committed",
      true,
    ],
    [
      { stage: "abandoned", allowed_actions: ["start_calibration"] },
      "ended",
      true,
    ],
  ] as const)("maps server state %# to %s", (state, mode, readOnly) => {
    expect(calibrationPresentation(state)).toEqual({ mode, readOnly });
  });

  it.each([
    ["tool_schema_repair_exhausted", "模型输出未通过格式校验"],
    ["token_limit_exceeded", "模型输出过长，未完成整理"],
    ["model_http_error", "本地模型调用失败"],
    ["model_timeout", "本地模型调用失败"],
    [null, "本地模型暂时无法完成整理"],
  ] as const)("maps calibration failure %s to parent-facing copy", (code, message) => {
    expect(calibrationFailureMessage(code)).toBe(message);
  });
});
