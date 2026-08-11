import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CircleDashed,
  LoaderCircle,
  Plus,
  RotateCw,
  Send,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";

import {
  ApiError,
  abandonCalibration,
  commitCalibration,
  createCalibration,
  getDemoScenario,
  getCalibration,
  getWeeklySummary,
  retryCalibration,
  simplifyCalibration,
} from "../api/client";
import {
  isCommitResponse,
  isProposalResponse,
  type CalibrationResponse,
  type CalibrationSubject,
  type CalibrationTaskType,
  type ModelRecovery,
  type ProposedObservation,
} from "../api/contracts";
import { currentWeekStart, formatDateTime } from "../date";
import { calibrationFailureMessage, calibrationPresentation } from "../workspace";

type CalibrationViewState = CalibrationResponse | ModelRecovery;
type Notice = { tone: "success" | "warning" | "error"; text: string } | null;
type SimplifiedRow = {
  subject: CalibrationSubject | "";
  taskType: CalibrationTaskType | "";
  conservativeMinutes: string;
};

const subjectLabels: Record<CalibrationSubject, string> = {
  chinese: "语文",
  mathematics: "数学",
  english: "英语",
  civics: "道德与法治",
  history: "历史",
  geography: "地理",
  biology: "生物",
};
const taskTypeLabels: Record<CalibrationTaskType, string> = {
  written: "书面作业",
  reading: "阅读",
  recitation: "背诵",
  correction: "订正",
  preparation: "预习",
  map_reading: "读图",
};
const subjectOptions = Object.entries(subjectLabels) as [CalibrationSubject, string][];
const taskTypeOptions = Object.entries(taskTypeLabels) as [CalibrationTaskType, string][];

function emptySimplifiedRow(): SimplifiedRow {
  return { subject: "", taskType: "", conservativeMinutes: "" };
}

const actionLabels = { assert: "新增", supersede: "替换", revoke: "撤销" } as const;
const categoryLabels = {
  subject_performance: "学科学习",
  task_speed: "任务速度",
  behavior: "学习行为",
  environment: "家庭安排",
} as const;
const metricLabels: Record<string, string> = {
  assessment_level: "掌握情况",
  score: "成绩",
  school_feedback: "学校反馈",
  foundation: "基础情况",
  typical_minutes_low: "通常用时下限",
  typical_minutes_high: "通常用时上限",
  estimated_actual_ratio: "估时偏差",
  start_avoidance: "启动回避",
  subject_overrun: "学科超时",
  late_omission: "较晚遗漏",
  start_confidence: "启动信心",
  sleep_boundary: "睡眠边界",
  arrival_time: "到家时间",
  fixed_activity: "固定活动",
  family_rule: "家庭规则",
};
const unitLabels: Record<string, string> = {
  points: "分",
  minutes: "分钟",
  ratio: "倍",
  count: "次",
  scale_1_5: "级",
  local_time: "",
};
const workloadLabels = { small: "小工作量", medium: "中等工作量", large: "大工作量" } as const;

function calibrationConfidence(sampleCount: number): string {
  if (sampleCount >= 5) return "较稳定";
  if (sampleCount >= 3) return "逐步校准";
  return "初步调整";
}

function observationValue(observation: ProposedObservation): string {
  if (observation.action === "revoke") return "撤销现有记录";
  if (observation.value_text !== null) return observation.value_text;
  if (observation.value_number !== null) {
    return `${observation.value_number}${observation.unit ? unitLabels[observation.unit] ?? observation.unit : ""}`;
  }
  return "-";
}

function hasAction(state: CalibrationViewState, action: string): boolean {
  return (state.allowed_actions as readonly string[]).includes(action);
}

function recoveryFailureCode(state: CalibrationViewState): string | null {
  if ("data" in state && state.data.kind === "calibration_recovery") {
    return state.data.failure_code;
  }
  return "failure_code" in state ? state.failure_code : null;
}

export function CalibrationView() {
  const queryClient = useQueryClient();
  const weekStart = useMemo(() => currentWeekStart(), []);
  const [observationText, setObservationText] = useState("");
  const [active, setActive] = useState<CalibrationViewState>();
  const [startingNew, setStartingNew] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmed, setConfirmed] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [demoPresetLoaded, setDemoPresetLoaded] = useState(false);
  const [showSimplified, setShowSimplified] = useState(false);
  const [simplifiedRows, setSimplifiedRows] = useState<SimplifiedRow[]>([emptySimplifiedRow()]);
  const [simplifiedPresetLoaded, setSimplifiedPresetLoaded] = useState(false);
  const demoMode = import.meta.env.VITE_DEMO_MODE === "true";
  const demoQuery = useQuery({
    queryKey: ["demo", "scenario"],
    queryFn: getDemoScenario,
    enabled: demoMode,
    staleTime: Number.POSITIVE_INFINITY,
  });

  const weeklyQuery = useQuery({
    queryKey: ["weekly-summary", weekStart],
    queryFn: () => getWeeklySummary(weekStart),
  });
  const latestId = weeklyQuery.data?.data.latest_calibration?.calibration_id;
  const calibrationQuery = useQuery({
    queryKey: ["calibration", latestId],
    queryFn: () => getCalibration(latestId!),
    enabled: Boolean(latestId) && !startingNew,
  });

  useEffect(() => {
    if (calibrationQuery.data && !startingNew) setActive(calibrationQuery.data);
  }, [calibrationQuery.data, startingNew]);

  const proposal = active && "data" in active && isProposalResponse(active) ? active : undefined;
  const committed = active && "data" in active && isCommitResponse(active) ? active : undefined;
  const draftId = proposal?.data.draft.id;

  useEffect(() => {
    setSelectedIds(new Set());
    setConfirmed(false);
  }, [draftId]);

  async function restoreLatest(calibrationId: string) {
    const latest = await queryClient.fetchQuery({
      queryKey: ["calibration", calibrationId],
      queryFn: () => getCalibration(calibrationId),
    });
    setActive(latest);
  }

  function acceptError(error: unknown, fallback: string) {
    if (error instanceof ApiError && error.envelope.recovery) {
      setActive(error.envelope.recovery);
      setStartingNew(false);
      setNotice({ tone: "warning", text: "观察内容已保存，模型暂时不可用。" });
      void queryClient.invalidateQueries({ queryKey: ["weekly-summary", weekStart] });
      return true;
    }
    setNotice({ tone: "error", text: fallback });
    return false;
  }

  const createMutation = useMutation({
    mutationFn: createCalibration,
    onSuccess: (response) => {
      setActive(response);
      setStartingNew(false);
      setObservationText("");
      setNotice(null);
      void queryClient.invalidateQueries({ queryKey: ["weekly-summary", weekStart] });
    },
    onError: async (error) => {
      if (acceptError(error, "暂时无法生成校准建议，请稍后重试。")) return;
      if (error instanceof ApiError && error.status === 409) {
        await weeklyQuery.refetch();
        setNotice({ tone: "warning", text: "规划参数版本已有更新，已刷新本周状态，请重新提交。" });
      }
    },
  });

  const retryMutation = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => retryCalibration(id, version),
    onSuccess: (response) => {
      setActive(response);
      setNotice(null);
      void queryClient.invalidateQueries({ queryKey: ["weekly-summary", weekStart] });
    },
    onError: async (error, input) => {
      if (acceptError(error, "重试未完成，请稍后再试。")) return;
      if (error instanceof ApiError && error.status === 409) {
        await restoreLatest(input.id);
        setNotice({ tone: "warning", text: "校准状态已有更新，已载入最新结果。" });
      }
    },
  });

  const commitMutation = useMutation({
    mutationFn: commitCalibration,
    onSuccess: (response) => {
      setActive(response);
      setNotice({ tone: "success", text: "所选校准项已确认生效。" });
      void queryClient.invalidateQueries({ queryKey: ["weekly-summary", weekStart] });
    },
    onError: async (error, input) => {
      if (acceptError(error, "暂时无法确认校准，请稍后重试。")) return;
      if (error instanceof ApiError && error.status === 409) {
        await restoreLatest(input.calibrationId);
        setNotice({ tone: "warning", text: "校准草案已有更新，已载入最新版本。" });
      }
    },
  });

  const simplifyMutation = useMutation({
    mutationFn: simplifyCalibration,
    onSuccess: (response) => {
      setActive(response);
      setShowSimplified(false);
      setNotice({ tone: "success", text: "简化校准已生成待确认建议，请核对后确认。" });
      void queryClient.invalidateQueries({ queryKey: ["weekly-summary", weekStart] });
    },
    onError: async (error, input) => {
      if (error instanceof ApiError && error.status === 409) {
        await restoreLatest(input.calibrationId);
        setShowSimplified(false);
        setNotice({ tone: "warning", text: "校准状态已有更新，已载入最新结果。" });
        return;
      }
      setNotice({ tone: "error", text: "暂时无法生成简化校准建议，请检查填写内容。" });
    },
  });

  const abandonMutation = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => abandonCalibration(id, version),
    onSuccess: (response) => {
      setActive(response);
      setShowSimplified(false);
      setNotice({ tone: "warning", text: "本次校准已放弃，规划参数没有变化。" });
      void queryClient.invalidateQueries({ queryKey: ["weekly-summary", weekStart] });
    },
    onError: async (error, input) => {
      if (error instanceof ApiError && error.status === 409) {
        await restoreLatest(input.id);
        setNotice({ tone: "warning", text: "校准状态已有更新，已载入最新结果。" });
        return;
      }
      setNotice({ tone: "error", text: "暂时无法放弃本次校准。" });
    },
  });

  const isBusy = createMutation.isPending || retryMutation.isPending || commitMutation.isPending
    || simplifyMutation.isPending || abandonMutation.isPending;
  const presentation = calibrationPresentation(active);

  function startNewCalibration() {
    setStartingNew(true);
    setActive(undefined);
    setObservationText("");
    setNotice(null);
    setShowSimplified(false);
    setSimplifiedRows([emptySimplifiedRow()]);
    setSimplifiedPresetLoaded(false);
  }

  function toggleOperation(operationId: string) {
    setConfirmed(false);
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(operationId)) next.delete(operationId);
      else next.add(operationId);
      return next;
    });
  }

  function abandon() {
    if (!active || !hasAction(active, "abandon_profile_patch")) return;
    if (!window.confirm("确认本周暂不更新？当前建议不会写入规划参数。")) return;
    abandonMutation.mutate({ id: active.calibration_id, version: active.calibration_version });
  }

  function updateSimplifiedRow(index: number, patch: Partial<SimplifiedRow>) {
    setSimplifiedRows((current) => current.map((row, rowIndex) => (
      rowIndex === index ? { ...row, ...patch } : row
    )));
    setSimplifiedPresetLoaded(false);
  }

  function loadSimplifiedPreset() {
    if (!demoQuery.data) return;
    setSimplifiedRows(demoQuery.data.weekly_calibration_groups.map((group) => ({
      subject: group.subject,
      taskType: group.task_type,
      conservativeMinutes: String(group.conservative_minutes),
    })));
    setSimplifiedPresetLoaded(true);
  }

  const simplifiedGroups = simplifiedRows.flatMap((row) => {
    const minutes = Number(row.conservativeMinutes);
    if (!row.subject || !row.taskType || !Number.isInteger(minutes) || minutes < 5 || minutes > 600) {
      return [];
    }
    return [{
      subject: row.subject,
      task_type: row.taskType,
      conservative_minutes: minutes,
    }];
  });
  const simplifiedValid = simplifiedGroups.length === simplifiedRows.length
    && simplifiedRows.length > 0
    && new Set(simplifiedGroups.map((group) => `${group.subject}:${group.task_type}`)).size === simplifiedRows.length;

  if (weeklyQuery.isPending) {
    return <main className="center-state"><LoaderCircle className="spin" size={26} /><strong>正在读取本周校准</strong></main>;
  }

  if (weeklyQuery.isError) {
    return (
      <main className="center-state">
        <strong>暂时无法读取本周状态</strong>
        <button className="button secondary" type="button" onClick={() => void weeklyQuery.refetch()}>
          <RotateCw size={17} /> 重新连接
        </button>
      </main>
    );
  }

  if (latestId && !startingNew && calibrationQuery.isPending && !active) {
    return <main className="center-state"><LoaderCircle className="spin" size={26} /><strong>正在恢复上次校准</strong></main>;
  }

  if (latestId && !startingNew && calibrationQuery.isError && !active) {
    return (
      <main className="center-state">
        <strong>暂时无法恢复上次校准</strong>
        <button className="button secondary" type="button" onClick={() => void calibrationQuery.refetch()}>
          <RotateCw size={17} /> 重新读取
        </button>
      </main>
    );
  }

  const profileVersion = weeklyQuery.data.data.profile_version;
  const showNew = startingNew || !active;

  return (
    <main className="page-shell calibration-page">
      <div className="page-heading compact-heading">
        <div>
          <span className="eyebrow"><SlidersHorizontal size={15} /> 家庭工作台</span>
          <h1>本周校准</h1>
          <p>{weeklyQuery.data.data.week_start} 至 {weeklyQuery.data.data.week_end}</p>
        </div>
        <div className="version-chip">当前规划参数 v{profileVersion}</div>
      </div>

      {notice && <div className={`notice ${notice.tone}`} role="status">{notice.text}</div>}

      {showNew ? (
        <section className="form-section calibration-form" aria-label="本周校准观察">
          <div className="section-heading">
            <div>
              <span className="section-kicker">自然语言观察</span>
              <h2>记录这一周的变化</h2>
            </div>
          </div>
          {demoMode && demoQuery.data ? (
            <div className="preset-row">
              <button
                className="button secondary"
                type="button"
                onClick={() => {
                  setObservationText(demoQuery.data.weekly_calibration_text);
                  setDemoPresetLoaded(true);
                }}
              >
                载入示例观察
              </button>
              {demoPresetLoaded ? <span className="preset-note">模拟数据，尚未保存</span> : null}
            </div>
          ) : null}
          <label>
            <span className="sr-only">本周观察</span>
            <textarea
              rows={7}
              maxLength={20_000}
              value={observationText}
              disabled={isBusy}
              placeholder="例如：这周数学口算通常 20 分钟能完成，英语听写开始前仍需要提醒。"
              onChange={(event) => setObservationText(event.target.value)}
            />
          </label>
          <div className="field-footer">
            <span>{observationText.length.toLocaleString("zh-CN")} / 20,000</span>
            <button
              className="button primary"
              type="button"
              disabled={isBusy || !observationText.trim()}
              onClick={() => createMutation.mutate({ text: observationText, expectedProfileVersion: profileVersion })}
            >
              {createMutation.isPending ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
              生成校准建议
            </button>
          </div>
        </section>
      ) : proposal && presentation.mode === "review" ? (
        <section className="proposal-section" aria-label="校准证据">
          <div className="section-heading proposal-heading">
            <div>
              <span className="section-kicker">待家长确认</span>
              <h2>建议变更 {proposal.data.draft.observations.length} 项</h2>
            </div>
            <span className="revision-label">校准 v{proposal.calibration_version}</span>
          </div>
          <div className="operation-list calibration-evidence-list">
            {proposal.data.draft.observations.map((observation) => {
              const detail = (proposal.data.calibration_details ?? []).find((item) => (
                item.subject === observation.subject && item.task_type === observation.task_type
              ));
              return (
              <label className="operation-row" key={observation.operation_id}>
                <input
                  type="checkbox"
                  checked={selectedIds.has(observation.operation_id)}
                  disabled={isBusy}
                  onChange={() => toggleOperation(observation.operation_id)}
                />
                <span className="operation-body">
                  <span className="operation-topline">
                    <span className={`action-tag ${observation.action}`}>{actionLabels[observation.action]}</span>
                    <strong>{observation.subject
                      ? subjectLabels[observation.subject as CalibrationSubject] ?? observation.subject
                      : categoryLabels[observation.category]}</strong>
                    {observation.task_type && (
                      <small>{taskTypeLabels[observation.task_type as CalibrationTaskType] ?? observation.task_type}</small>
                    )}
                  </span>
                  {detail ? (
                    <span className="calibration-detail">
                      <span>参考 {detail.reference_minutes} 分钟</span>
                      <span>观察 P80 {detail.observed_p80_minutes} 分钟</span>
                      <span>{detail.sample_count} 个样本 · {workloadLabels[detail.workload_band]}</span>
                      <b>建议 {detail.suggested_ratio.toFixed(2)} 倍</b>
                      <small>{calibrationConfidence(detail.sample_count)}</small>
                    </span>
                  ) : (
                    <span className="operation-detail">
                      <span>{metricLabels[observation.metric] ?? observation.metric}</span>
                      <b>{observationValue(observation)}</b>
                    </span>
                  )}
                </span>
              </label>
              );
            })}
          </div>

          {proposal.data.unapplied_notes.length > 0 && (
            <div className="unapplied-notes">
              <strong>本次未转换为规划参数的备注</strong>
              <ul>
                {proposal.data.unapplied_notes.map((note) => <li key={note}>{note}</li>)}
              </ul>
            </div>
          )}

          <label className={`confirmation-row ${selectedIds.size ? "" : "disabled"}`}>
            <input
              type="checkbox"
              checked={confirmed}
              disabled={!selectedIds.size || isBusy}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>我已核对并确认应用所选 {selectedIds.size} 项变更</span>
          </label>

          <div className="action-row split-actions">
            {proposal.allowed_actions.includes("abandon_profile_patch") && (
              <button className="button danger-quiet" type="button" disabled={isBusy} onClick={abandon}>
                <Trash2 size={17} /> 放弃本次
              </button>
            )}
            <button
              className="button primary"
              type="button"
              disabled={isBusy || !confirmed || selectedIds.size === 0}
              onClick={() => commitMutation.mutate({
                calibrationId: proposal.calibration_id,
                expectedCalibrationVersion: proposal.calibration_version,
                draftId: proposal.data.draft.id,
                draftDigest: proposal.data.draft.draft_digest,
                acceptedOperationIds: [...selectedIds],
              })}
            >
              {commitMutation.isPending ? <LoaderCircle className="spin" size={18} /> : <Check size={18} />}
              确认所选变更
            </button>
          </div>
        </section>
      ) : committed && presentation.mode === "committed" ? (
        <section className="result-state committed-state">
          <CheckCircle2 size={30} />
          <div>
            <span className="section-kicker green">校准已完成</span>
            <h2>规划参数已更新至 v{committed.data.commit.profile_version}</h2>
            <p>已确认 {committed.data.accepted_operation_ids.length} 项变更 · {formatDateTime(committed.data.commit.committed_at)}</p>
          </div>
          {committed.allowed_actions.includes("start_calibration") && (
            <button className="button secondary" type="button" onClick={startNewCalibration}>
              <Plus size={17} /> 开始新的校准
            </button>
          )}
        </section>
      ) : active.stage === "abandoned" ? (
        <section className="result-state ended-state">
          <CircleDashed size={30} />
          <div>
            <span className="section-kicker">本次已结束</span>
            <h2>规划参数没有变化</h2>
            <p>已放弃本次校准建议。</p>
          </div>
          {active.allowed_actions.includes("start_calibration") && (
            <button className="button secondary" type="button" onClick={startNewCalibration}>
              <Plus size={17} /> 开始新的校准
            </button>
          )}
        </section>
      ) : (
        <section className={`result-state recovery-state ${showSimplified ? "with-fallback" : ""}`} aria-label="校准恢复">
          <AlertTriangle size={30} />
          <div>
            <span className="section-kicker warning">已保存观察</span>
            <h2>{active.stage === "model_unavailable"
              ? calibrationFailureMessage(recoveryFailureCode(active))
              : "校准正在恢复"}</h2>
            <p>原始观察已保存，规划参数没有改变。校准版本 v{active.calibration_version}。</p>
          </div>
          <div className="recovery-actions">
            {hasAction(active, "retry_last_turn") && (
              <button
                className="button primary"
                type="button"
                disabled={isBusy}
                onClick={() => retryMutation.mutate({ id: active.calibration_id, version: active.calibration_version })}
              >
                {retryMutation.isPending ? <LoaderCircle className="spin" size={18} /> : <RotateCw size={17} />}
                重试一次
              </button>
            )}
            {hasAction(active, "use_simplified_calibration") && (
              <button
                className="button secondary"
                type="button"
                disabled={isBusy}
                onClick={() => setShowSimplified((current) => !current)}
              >
                <SlidersHorizontal size={17} /> 使用简化校准
              </button>
            )}
            {hasAction(active, "abandon_profile_patch") && (
              <button className="button danger-quiet" type="button" disabled={isBusy} onClick={abandon}>
                <Trash2 size={17} /> 本周暂不更新
              </button>
            )}
          </div>
          {showSimplified && (
            <div className="simplified-calibration">
              <div className="fallback-heading">
                <div>
                  <span className="section-kicker">确定性降级</span>
                  <h3>填写保守完成时间</h3>
                  <p>这些数据不会调用模型；提交后仍需家长核对确认才会生效。</p>
                </div>
                {demoMode && demoQuery.data && (
                  <div className="preset-inline">
                    <button className="button secondary" type="button" onClick={loadSimplifiedPreset}>
                      载入演示预设
                    </button>
                    {simplifiedPresetLoaded && <span className="preset-note">模拟数据，尚未保存</span>}
                  </div>
                )}
              </div>
              <div className="simplified-rows">
                {simplifiedRows.map((row, index) => (
                  <div className="simplified-row" key={index}>
                    <label>
                      <span>科目</span>
                      <select
                        value={row.subject}
                        disabled={isBusy}
                        onChange={(event) => updateSimplifiedRow(index, {
                          subject: event.target.value as CalibrationSubject | "",
                        })}
                      >
                        <option value="">请选择</option>
                        {subjectOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>任务类型</span>
                      <select
                        value={row.taskType}
                        disabled={isBusy}
                        onChange={(event) => updateSimplifiedRow(index, {
                          taskType: event.target.value as CalibrationTaskType | "",
                        })}
                      >
                        <option value="">请选择</option>
                        {taskTypeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>保守分钟</span>
                      <input
                        type="number"
                        min={5}
                        max={600}
                        step={1}
                        value={row.conservativeMinutes}
                        disabled={isBusy}
                        onChange={(event) => updateSimplifiedRow(index, {
                          conservativeMinutes: event.target.value,
                        })}
                      />
                    </label>
                    <button
                      className="icon-button danger-quiet"
                      type="button"
                      aria-label={`删除第 ${index + 1} 行`}
                      title="删除此行"
                      disabled={isBusy || simplifiedRows.length === 1}
                      onClick={() => setSimplifiedRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                ))}
              </div>
              <div className="fallback-actions">
                <button
                  className="button secondary"
                  type="button"
                  disabled={isBusy || simplifiedRows.length >= 8}
                  onClick={() => {
                    setSimplifiedRows((current) => [...current, emptySimplifiedRow()]);
                    setSimplifiedPresetLoaded(false);
                  }}
                >
                  <Plus size={17} /> 增加一行
                </button>
                <button
                  className="button primary"
                  type="button"
                  disabled={isBusy || !simplifiedValid}
                  onClick={() => simplifyMutation.mutate({
                    calibrationId: active.calibration_id,
                    expectedCalibrationVersion: active.calibration_version,
                    durationGroups: simplifiedGroups,
                  })}
                >
                  {simplifyMutation.isPending ? <LoaderCircle className="spin" size={18} /> : <Check size={18} />}
                  生成待确认建议
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
