export type ParentPath = "/brief" | "/calibration" | "/result";

export type CalibrationStage =
  | "input_saved"
  | "model_unavailable"
  | "needs_confirmation"
  | "retry_pending"
  | "committed"
  | "abandoned";

export type CalibrationAction =
  | "generate_profile_patch"
  | "retry_last_turn"
  | "use_simplified_calibration"
  | "commit_profile_patch"
  | "revise_profile_patch"
  | "abandon_profile_patch"
  | "start_calibration";

type CalibrationStateLike = {
  stage: CalibrationStage;
  allowed_actions: readonly CalibrationAction[];
};

export function canonicalParentPath(pathname: string): ParentPath {
  if (pathname === "/calibration" || pathname === "/result") return pathname;
  return "/brief";
}

export function eveningRecordStatus(
  stage: string,
  sessionDate: string,
  today: string,
): "archived" | "incomplete" | "in_progress" {
  if (stage === "closed") return "archived";
  if (sessionDate < today) return "incomplete";
  return "in_progress";
}

export function calibrationPresentation(state?: CalibrationStateLike): {
  mode: "new" | "review" | "recovery" | "committed" | "ended";
  readOnly: boolean;
} {
  if (!state) return { mode: "new", readOnly: false };
  if (state.stage === "needs_confirmation") return { mode: "review", readOnly: false };
  if (state.stage === "committed") return { mode: "committed", readOnly: true };
  if (state.stage === "abandoned") return { mode: "ended", readOnly: true };
  return { mode: "recovery", readOnly: false };
}

export function calibrationFailureMessage(failureCode: string | null): string {
  if (failureCode === "tool_schema_repair_exhausted") {
    return "模型输出未通过格式校验";
  }
  if (failureCode === "token_limit_exceeded" || failureCode === "model_output_truncated") {
    return "模型输出过长，未完成整理";
  }
  if (
    failureCode === "model_http_error" ||
    failureCode === "model_timeout" ||
    failureCode === "model_connection_error"
  ) {
    return "本地模型调用失败";
  }
  return "本地模型暂时无法完成整理";
}
