import { z } from "zod";

const DateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const DateTimeSchema = z.string().datetime({ offset: true });
const Sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);

const DeliverySchema = z.object({ replayed: z.boolean() }).strict();

export const CalibrationSubjectSchema = z.enum([
  "chinese",
  "mathematics",
  "english",
  "civics",
  "history",
  "geography",
  "biology",
]);

export const CalibrationTaskTypeSchema = z.enum([
  "written",
  "reading",
  "recitation",
  "correction",
  "preparation",
  "map_reading",
]);

const SimplifiedDurationGroupSchema = z
  .object({
    subject: CalibrationSubjectSchema,
    task_type: CalibrationTaskTypeSchema,
    conservative_minutes: z.number().int().min(5).max(600),
  })
  .strict();

export const DemoScenarioSchema = z
  .object({
    scenario_id: z.string(),
    label: z.string(),
    planning_date: DateSchema,
    start_time: z.string(),
    sleep_time: z.string(),
    school_brief_text: z.string(),
    child_report_text: z.string(),
    weekly_calibration_text: z.string(),
    weekly_calibration_groups: z.array(SimplifiedDurationGroupSchema),
  })
  .strict();

export const CalibrationStageSchema = z.enum([
  "input_saved",
  "model_unavailable",
  "needs_confirmation",
  "retry_pending",
  "committed",
  "abandoned",
]);

export const CalibrationActionSchema = z.enum([
  "generate_profile_patch",
  "retry_last_turn",
  "use_simplified_calibration",
  "commit_profile_patch",
  "revise_profile_patch",
  "abandon_profile_patch",
  "start_calibration",
]);

export const SchoolBriefRevisionSchema = z
  .object({
    id: z.string().min(1),
    brief_date: DateSchema,
    revision: z.number().int().positive(),
    content_sha256: Sha256Schema,
    raw_text: z.string(),
    source: z.literal("manual-paste"),
    created_at: DateTimeSchema,
  })
  .strict();

export const SchoolBriefReadEnvelopeSchema = z
  .object({
    trace_id: z.string().min(1),
    data: SchoolBriefRevisionSchema,
  })
  .strict();

export const SchoolBriefWriteEnvelopeSchema = z
  .object({
    trace_id: z.string().min(1),
    data: z
      .object({
        brief_date: DateSchema,
        revision: z.number().int().positive(),
        record: SchoolBriefRevisionSchema,
        trace_id: z.string().min(1),
        no_op: z.boolean(),
        allowed_actions: z.array(z.literal("replace_school_brief")),
      })
      .strict(),
    delivery: DeliverySchema,
  })
  .strict();

const CalibrationSummarySchema = z
  .object({
    calibration_id: z.string().min(1),
    calibration_version: z.number().int().positive(),
    profile_version: z.number().int().nonnegative(),
    state: CalibrationStageSchema,
    occurred_at: DateTimeSchema,
  })
  .strict();

const NoDataMetricSchema = z
  .object({
    value: z.null(),
    numerator: z.literal(0),
    denominator: z.literal(0),
    status: z.literal("no_data"),
  })
  .strict();

export const WeeklySummaryEnvelopeSchema = z
  .object({
    trace_id: z.string().min(1),
    data: z
      .object({
        week_start: DateSchema,
        week_end: DateSchema,
        profile_version: z.number().int().nonnegative(),
        latest_calibration: CalibrationSummarySchema.nullable(),
        confirmed_observation_count: z.number().int().nonnegative(),
        estimate_error: NoDataMetricSchema,
        omissions: NoDataMetricSchema,
        start_confidence: NoDataMetricSchema,
        parent_interventions: NoDataMetricSchema,
      })
      .strict(),
  })
  .strict();

const EveningTaskSchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    subject: z.string().nullable(),
    completion_state: z.enum(["pending", "partial", "completed", "uncertain", "no_task"]),
    conservative_minutes: z.number().int().nonnegative(),
    must_do_tonight: z.boolean(),
  });

const EveningCapacitySchema = z.object({
  shortfall_minutes: z.number().int().nonnegative(),
  feasible: z.boolean(),
});

const EveningPaceTargetSchema = z.object({
  task_id: z.string().min(1),
  conservative_minutes: z.number().int().nonnegative(),
  target_minutes: z.number().int().nonnegative(),
});

const EveningCapacityRecoverySchema = z.object({
  mode: z.enum(["start_earlier", "focus_pace", "manual_choice"]),
  baseline_shortfall_minutes: z.number().int().positive(),
  recommended_start_time: z.string(),
  speedup_percent: z.number().int().min(0).max(20),
  pace_targets: z.array(EveningPaceTargetSchema),
  residual_shortfall_minutes: z.number().int().nonnegative(),
});

const EveningPlanSchema = z
  .object({
    id: z.string().min(1),
    committed: z.boolean(),
    ordered_task_ids: z.array(z.string()),
    deferred_task_ids: z.array(z.string()),
    deadline_risk_task_ids: z.array(z.string()),
    pace_targets: z.array(EveningPaceTargetSchema),
    capacity_recovery: EveningCapacityRecoverySchema.nullable(),
    predicted_finish_at: DateTimeSchema.nullable(),
    true_surplus_minutes: z.number().int().nonnegative(),
    capacity: EveningCapacitySchema,
    baseline_capacity: EveningCapacitySchema,
  });

const EveningOutcomeSchema = z
  .object({
    task_id: z.string().min(1),
    completion_state: z.enum(["pending", "partial", "completed", "uncertain", "no_task"]),
    actual_minutes: z.number().int().nonnegative().nullable(),
    note: z.string().nullable(),
  });

export const EveningResultSchema = z
  .object({
    session_id: z.string().min(1),
    session_date: DateSchema,
    version: z.number().int().nonnegative(),
    stage: z.enum([
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
    ]),
    trace_id: z.string().min(1),
    data: z.object({
      inventory: z.array(EveningTaskSchema),
      plan: EveningPlanSchema.nullable(),
      outcomes: z.array(EveningOutcomeSchema),
    }),
  });

const ProposedObservationSchema = z
  .object({
    action: z.enum(["assert", "supersede", "revoke"]),
    category: z.enum(["subject_performance", "task_speed", "behavior", "environment"]),
    subject: z.string().nullable(),
    task_type: z.string().nullable(),
    metric: z.string().min(1),
    value_text: z.string().nullable(),
    value_number: z.number().nullable(),
    unit: z.string().nullable(),
    confidence: z.number().min(0).max(1),
    sample_count: z.number().int().positive().nullable(),
    observed_at: DateTimeSchema,
    target_event_id: z.string().nullable(),
    operation_id: z.string().min(1),
  })
  .strict();

const ProfilePatchDraftSchema = z
  .object({
    id: z.string().min(1),
    calibration_id: z.string().min(1),
    receipt_id: z.string().min(1),
    base_profile_version: z.number().int().nonnegative(),
    proposal_digest: Sha256Schema,
    draft_digest: Sha256Schema,
    observations: z.array(ProposedObservationSchema).min(1),
    revises_draft_id: z.string().nullable(),
    created_at: DateTimeSchema,
  })
  .strict();

const ProposalDataSchema = z
  .object({
    kind: z.literal("profile_patch_proposal"),
    draft: ProfilePatchDraftSchema,
    diff_preview: z.array(ProposedObservationSchema),
    narration: z.string().nullable(),
    narration_status: z.enum(["available", "unavailable", "not_requested"]),
    unapplied_notes: z.array(z.string()),
    calibration_details: z.array(
      z.object({
        subject: CalibrationSubjectSchema,
        task_type: CalibrationTaskTypeSchema,
        workload_band: z.enum(["small", "medium", "large"]),
        reference_minutes: z.number().int().min(5).max(600),
        observed_p80_minutes: z.number().int().min(5).max(600),
        sample_count: z.number().int().min(1).max(8),
        suggested_ratio: z.number().min(0.1).max(10),
      }).strict(),
    ).optional(),
  })
  .strict();

const CommitDataSchema = z
  .object({
    kind: z.literal("profile_patch_commit"),
    commit: z
      .object({
        id: z.string().min(1),
        calibration_id: z.string().min(1),
        draft_id: z.string().min(1),
        profile_version: z.number().int().positive(),
        accepted_operation_ids: z.array(z.string().min(1)).min(1),
        confirmed_by: z.string().min(1),
        committed_at: DateTimeSchema,
      })
      .strict(),
    draft_digest: Sha256Schema,
    accepted_operation_ids: z.array(z.string().min(1)).min(1),
    observation_event_ids: z.array(z.string().min(1)).min(1),
    narration: z.string().nullable(),
    narration_status: z.enum(["available", "unavailable", "not_requested"]),
  })
  .strict();

const RecoveryDataSchema = z
  .object({
    kind: z.literal("calibration_recovery"),
    input_saved: z.literal(true),
    input_receipt_id: z.string().min(1),
    resume_stage: z.enum(["profile_propose", "profile_commit"]).nullable(),
    pending_kind: z.enum(["profile_patch", "model_retry"]).nullable(),
    pending_entity_id: z.string().nullable(),
    failure_code: z.string().nullable(),
  })
  .strict();

export const CalibrationResponseSchema = z
  .object({
    calibration_id: z.string().min(1),
    calibration_version: z.number().int().positive(),
    profile_version: z.number().int().nonnegative(),
    stage: CalibrationStageSchema,
    allowed_actions: z.array(CalibrationActionSchema),
    trace_id: z.string().min(1),
    data: z.discriminatedUnion("kind", [ProposalDataSchema, CommitDataSchema, RecoveryDataSchema]),
    delivery: DeliverySchema,
  })
  .strict();

const ModelRecoverySchema = z
  .object({
    calibration_id: z.string().min(1),
    calibration_version: z.number().int().positive(),
    profile_version: z.number().int().nonnegative(),
    stage: z.literal("model_unavailable"),
    allowed_actions: z.tuple([
      z.literal("retry_last_turn"),
      z.literal("use_simplified_calibration"),
      z.literal("abandon_profile_patch"),
    ]),
    resume_stage: z.enum(["profile_propose", "profile_commit"]),
    pending_kind: z.literal("model_retry"),
    pending_entity_id: z.string().min(1),
    input_receipt_id: z.string().min(1),
    input_saved: z.literal(true),
    failure_code: z.string().nullable(),
  })
  .strict();

export const ApiErrorEnvelopeSchema = z
  .object({
    error: z
      .object({
        code: z.enum([
          "schema_invalid",
          "not_found",
          "method_not_allowed",
          "version_conflict",
          "idempotency_conflict",
          "invalid_transition",
          "draft_digest_mismatch",
          "commit_command_invalid",
          "profile_proposal_invalid",
          "retry_lineage_conflict",
          "model_protocol_error",
          "model_unavailable",
          "internal_error",
        ]),
        message: z.string().min(1),
        issues: z.array(
          z
            .object({
              location: z.array(z.union([z.string(), z.number().int()])),
              type: z.string().min(1),
            })
            .strict(),
        ),
      })
      .strict(),
    trace_id: z.string().min(1),
    recovery: ModelRecoverySchema.nullable(),
  })
  .strict();

export type SchoolBriefRevision = z.infer<typeof SchoolBriefRevisionSchema>;
export type DemoScenario = z.infer<typeof DemoScenarioSchema>;
export type CalibrationSubject = z.infer<typeof CalibrationSubjectSchema>;
export type CalibrationTaskType = z.infer<typeof CalibrationTaskTypeSchema>;
export type SimplifiedDurationGroup = z.infer<typeof SimplifiedDurationGroupSchema>;
export type SchoolBriefWriteEnvelope = z.infer<typeof SchoolBriefWriteEnvelopeSchema>;
export type WeeklySummaryEnvelope = z.infer<typeof WeeklySummaryEnvelopeSchema>;
export type EveningResult = z.infer<typeof EveningResultSchema>;
export type CalibrationResponse = z.infer<typeof CalibrationResponseSchema>;
export type ModelRecovery = z.infer<typeof ModelRecoverySchema>;
export type ApiErrorEnvelope = z.infer<typeof ApiErrorEnvelopeSchema>;
export type ProposedObservation = z.infer<typeof ProposedObservationSchema>;

export function isProposalResponse(
  response: CalibrationResponse,
): response is CalibrationResponse & { data: z.infer<typeof ProposalDataSchema> } {
  return response.data.kind === "profile_patch_proposal";
}

export function isCommitResponse(
  response: CalibrationResponse,
): response is CalibrationResponse & { data: z.infer<typeof CommitDataSchema> } {
  return response.data.kind === "profile_patch_commit";
}
