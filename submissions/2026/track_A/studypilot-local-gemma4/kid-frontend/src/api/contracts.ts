import { z } from "zod";

export const SessionStageSchema = z.enum([
  "created",
  "intake_draft",
  "coverage_pending",
  "inventory_confirmed",
  "plan_draft",
  "committed",
  "closed",
  "capacity_conflict",
  "needs_confirmation",
  "model_unavailable",
]);

export const CompletionStateSchema = z.enum([
  "pending",
  "partial",
  "completed",
  "uncertain",
  "no_task",
]);

const IntakeDraftTaskSchema = z.object({
  title: z.string(),
  subject: z.string().nullable(),
  completion_state: CompletionStateSchema,
  child_estimate_minutes: z.number().int().nonnegative().nullable(),
  deadline_text: z.string().nullable(),
  total_units: z.number().int().positive().nullable(),
  completed_units: z.number().int().nonnegative().nullable(),
  notes: z.string().nullable(),
});

const InventoryTaskSchema = z.object({
  id: z.string(),
  title: z.string(),
  subject: z.string().nullable(),
  task_type: z.string().nullable(),
  completion_state: CompletionStateSchema,
  estimated_minutes: z.number().int().nonnegative(),
  conservative_minutes: z.number().int().nonnegative(),
  priority: z.number().int().nonnegative(),
  must_do_tonight: z.boolean(),
  due_at: z.string().nullable(),
  child_estimate_minutes: z.number().int().nonnegative().nullable(),
  estimate_source: z.enum([
    "history_p80",
    "parent_range",
    "child_adjusted",
    "domain_default",
  ]),
  estimate_confidence: z.enum(["low", "medium", "high"]),
  notes: z.string().nullable(),
  assignment_id: z.string().nullable(),
  deadline_text: z.string().nullable(),
  remaining_percent: z.number().int().min(0).max(100),
  planning_bucket: z.enum(["tonight_required", "tonight_advance", "future_scheduled"]),
  planned_evening_date: z.string().nullable(),
  estimate_breakdown: z.array(
    z.object({
      component: z.string(),
      label: z.string(),
      task_type: z.string(),
      remaining_quantity: z.number().int().nonnegative().nullable(),
      unit: z.string().nullable(),
      reference_minutes: z.number().int().nonnegative(),
      calibrated_minutes: z.number().int().nonnegative(),
      source: z.enum(["history_p80", "parent_range", "child_adjusted", "domain_default"]),
      confidence: z.enum(["low", "medium", "high"]),
    }),
  ).optional(),
  estimate_signature: z.string().nullable().optional(),
});

const TimeBoundarySchema = z.object({
  start_time: z.string(),
  sleep_time: z.string(),
  gross_minutes: z.number().int().positive(),
  fixed_minutes: z.number().int().nonnegative(),
  net_minutes: z.number().int().nonnegative(),
});

const FutureAssignmentSchema = z.object({
  assignment_id: z.string(),
  title: z.string(),
  subject: z.string().nullable(),
  deadline_text: z.string().nullable(),
  due_at: z.string().nullable(),
  planned_evening_date: z.string(),
  remaining_percent: z.number().int().positive().max(100),
  latest_change_reason: z.string().nullable(),
});

const CapacitySchema = z.object({
  available_minutes: z.number().int().nonnegative(),
  fixed_minutes: z.number().int().nonnegative(),
  task_minutes: z.number().int().nonnegative(),
  buffer_minutes: z.number().int().nonnegative(),
  required_minutes: z.number().int().nonnegative(),
  remaining_minutes: z.number().int().nonnegative(),
  shortfall_minutes: z.number().int().nonnegative(),
  feasible: z.boolean(),
});

const PaceTargetSchema = z.object({
  task_id: z.string(),
  conservative_minutes: z.number().int().nonnegative(),
  target_minutes: z.number().int().nonnegative(),
});

const CapacityRecoverySchema = z.object({
  mode: z.enum(["start_earlier", "focus_pace", "manual_choice"]),
  baseline_shortfall_minutes: z.number().int().positive(),
  earliest_start_time: z.string(),
  recommended_start_time: z.string(),
  speedup_percent: z.number().int().min(0).max(20),
  pace_targets: z.array(PaceTargetSchema),
  recovered_minutes: z.number().int().nonnegative(),
  residual_shortfall_minutes: z.number().int().nonnegative(),
});

const PlanBlockSchema = z.object({
  id: z.string(),
  block_type: z.enum(["task", "fixed", "buffer", "break"]),
  label: z.string(),
  starts_at: z.string(),
  ends_at: z.string(),
  ordinal: z.number().int().nonnegative(),
  task_id: z.string().nullable(),
});

const PlanSchema = z.object({
  id: z.string(),
  plan_version: z.number().int().positive(),
  capacity: CapacitySchema,
  baseline_capacity: CapacitySchema,
  blocks: z.array(PlanBlockSchema),
  ordered_task_ids: z.array(z.string()),
  deferred_task_ids: z.array(z.string()),
  future_scheduled_task_ids: z.array(z.string()),
  deadline_risk_task_ids: z.array(z.string()),
  capacity_recovery: CapacityRecoverySchema.nullable(),
  pace_targets: z.array(PaceTargetSchema),
  reason: z.string(),
  committed: z.boolean(),
  scheduled_optional_minutes: z.number().int().nonnegative(),
  true_surplus_minutes: z.number().int().nonnegative(),
  predicted_finish_at: z.string().nullable(),
});

const OutcomeSchema = z.object({
  id: z.string(),
  task_id: z.string(),
  completion_state: CompletionStateSchema,
  actual_minutes: z.number().int().nonnegative().nullable(),
  note: z.string().nullable(),
});

export const EveningResponseSchema = z.object({
  session_id: z.string(),
  session_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  planning_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  version: z.number().int().nonnegative(),
  stage: SessionStageSchema,
  allowed_actions: z.array(z.string()),
  trace_id: z.string(),
  data: z.object({
    narration: z.string().nullable(),
    intake_draft: z
      .object({
        id: z.string(),
        tasks: z.array(IntakeDraftTaskSchema),
        coverage_notes: z.array(z.string()).default([]),
      })
      .nullable(),
    coverage_mode: z.enum(["school_verified", "child_reported"]).nullable(),
    inventory: z.array(InventoryTaskSchema),
    plan: PlanSchema.nullable(),
    outcomes: z.array(OutcomeSchema),
    time_boundary: TimeBoundarySchema,
    future_assignments: z.array(FutureAssignmentSchema),
  }),
});

export const DemoScenarioSchema = z
  .object({
    scenario_id: z.string(),
    label: z.string(),
    planning_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    start_time: z.string(),
    sleep_time: z.string(),
    school_brief_text: z.string(),
    child_report_text: z.string(),
    weekly_calibration_text: z.string(),
    weekly_calibration_groups: z.array(
      z
        .object({
          subject: z.enum([
            "chinese",
            "mathematics",
            "english",
            "civics",
            "history",
            "geography",
            "biology",
          ]),
          task_type: z.enum([
            "written",
            "reading",
            "recitation",
            "correction",
            "preparation",
            "map_reading",
          ]),
          conservative_minutes: z.number().int().min(5).max(600),
        })
        .strict(),
    ),
  })
  .strict();

export const ApiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
  }),
  trace_id: z.string().optional(),
});

export type SessionStage = z.infer<typeof SessionStageSchema>;
export type CompletionState = z.infer<typeof CompletionStateSchema>;
export type EveningResponse = z.infer<typeof EveningResponseSchema>;
export type DemoScenario = z.infer<typeof DemoScenarioSchema>;
export type IntakeDraftTask = z.infer<typeof IntakeDraftTaskSchema>;
export type InventoryTask = z.infer<typeof InventoryTaskSchema>;
export type EveningPlan = z.infer<typeof PlanSchema>;
export type CapacityRecovery = z.infer<typeof CapacityRecoverySchema>;
export type PaceTarget = z.infer<typeof PaceTargetSchema>;
export type PlanBlock = z.infer<typeof PlanBlockSchema>;
export type Outcome = z.infer<typeof OutcomeSchema>;
