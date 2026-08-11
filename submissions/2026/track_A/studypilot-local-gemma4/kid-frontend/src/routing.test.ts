import { describe, expect, it } from "vitest";

import { canonicalPathForStage } from "./routing";

describe("canonicalPathForStage", () => {
  it.each([
    ["created", "/intake"],
    ["intake_draft", "/intake"],
    ["model_unavailable", "/intake"],
    ["coverage_pending", "/intake"],
    ["needs_confirmation", "/intake"],
    ["inventory_confirmed", "/overview"],
    ["capacity_conflict", "/overview"],
    ["plan_draft", "/route"],
    ["committed", "/route"],
    ["closed", "/review"],
  ] as const)("maps %s to %s", (stage, path) => {
    expect(canonicalPathForStage(stage)).toBe(path);
  });
});
