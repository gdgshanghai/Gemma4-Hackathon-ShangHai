import type { SessionStage } from "./api/contracts";

export type AppPath = "/intake" | "/overview" | "/route" | "/review";

const STAGE_PATHS: Record<SessionStage, AppPath> = {
  created: "/intake",
  intake_draft: "/intake",
  model_unavailable: "/intake",
  coverage_pending: "/intake",
  needs_confirmation: "/intake",
  inventory_confirmed: "/overview",
  capacity_conflict: "/overview",
  plan_draft: "/route",
  committed: "/route",
  closed: "/review",
};

export function canonicalPathForStage(stage: SessionStage): AppPath {
  return STAGE_PATHS[stage];
}
