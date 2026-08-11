import { useState } from "react";
import { Calculator, CheckCircle2, Route } from "lucide-react";

import { createPlan, updateTimeBoundary } from "../api/client";
import { CapacityRecoveryPanel } from "../components/CapacityRecoveryPanel";
import { InventoryTaskRows } from "../components/TaskRows";
import { TimeBoundaryEditor } from "../components/TimeBoundaryEditor";
import { useSession } from "../state/session";

export function OverviewView() {
  const { session, acceptResponse, handleActionError } = useSession();
  const [pending, setPending] = useState(false);
  const conflict = session?.stage === "capacity_conflict" ? session.data.plan : null;
  if (!session) return null;
  const currentSession = session;

  const inventory = currentSession.data.inventory;
  const completed = inventory.filter((task) => task.completion_state === "completed" || task.completion_state === "no_task");
  const mustDo = inventory.filter((task) => task.must_do_tonight && !completed.includes(task));
  const futureTasks = inventory.filter((task) => task.planning_bucket === "future_scheduled");
  const optional = inventory.filter((task) =>
    !task.must_do_tonight && task.planning_bucket !== "future_scheduled" && !completed.includes(task));
  const totalMinutes = mustDo.reduce((sum, task) => sum + task.conservative_minutes, 0);
  const capacityFacts = [
    { label: "学习窗口", value: currentSession.data.time_boundary.gross_minutes, note: "总时间窗口" },
    { label: "固定事项", value: currentSession.data.time_boundary.fixed_minutes },
    { label: "净可安排", value: currentSession.data.time_boundary.net_minutes },
    { label: "保守任务用时", value: totalMinutes },
  ];

  async function buildPlan() {
    setPending(true);
    try {
      acceptResponse(await createPlan(currentSession.session_id, currentSession.version, "initial"));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  async function applyStartAndPlan(reason: "initial" | "focus_pace") {
    const recovery = conflict?.capacity_recovery;
    if (!recovery) return;
    setPending(true);
    try {
      const updated = await updateTimeBoundary(
        currentSession.session_id,
        currentSession.version,
        recovery.recommended_start_time,
        currentSession.data.time_boundary.sleep_time,
      );
      acceptResponse(await createPlan(currentSession.session_id, updated.version, reason));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  async function applyManualChoice(taskIds: string[]) {
    if (!taskIds.length) return;
    setPending(true);
    try {
      acceptResponse(await createPlan(
        currentSession.session_id,
        currentSession.version,
        "manual_deadline_risk",
        undefined,
        taskIds,
      ));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="page-shell">
      <div className="page-heading">
        <span className="eyebrow"><Calculator size={17} />今晚全貌</span>
        <h1>{conflict ? "今晚需要调整时间安排" : "今晚的任务已经看清"}</h1>
        <p>{currentSession.data.coverage_mode === "school_verified" ? "已对照学校作业单" : "依据你提供的清单"}</p>
      </div>

      <TimeBoundaryEditor />

      {conflict?.capacity_recovery ? (
        <CapacityRecoveryPanel
          key={conflict.id}
          recovery={conflict.capacity_recovery}
          tasks={conflict.ordered_task_ids
            .map((taskId) => inventory.find((task) => task.id === taskId))
            .filter((task): task is NonNullable<typeof task> => Boolean(task))}
          pending={pending}
          onStartEarlier={() => void applyStartAndPlan("initial")}
          onAcceptFocus={() => void applyStartAndPlan("focus_pace")}
          onManualChoice={(taskIds) => void applyManualChoice(taskIds)}
        />
      ) : conflict ? (
        <div className="attention-callout" role="status">
          <strong>这份旧计划需要重新计算</strong>
          <span>任务记录仍然保留，重新生成后会使用新的截止日期保护规则。</span>
          <button className="button secondary" type="button" disabled={pending} onClick={() => void buildPlan()}>
            重新计算
          </button>
        </div>
      ) : null}

      <section className="capacity-strip" aria-label="今晚容量证明">
        {capacityFacts.map((fact) => (
          <div key={fact.label}>
            <span>{fact.label}</span>
            <strong>{fact.value} 分钟</strong>
            {fact.note ? <small>{fact.note}</small> : null}
          </div>
        ))}
        {conflict ? <div className="shortfall"><span>真实缺口</span><strong>{conflict.capacity.shortfall_minutes} 分钟</strong></div> : null}
      </section>

      <div className="overview-task-grid">
        <div className="overview-primary-tasks">
          {mustDo.length ? (
            <section className="page-section" aria-labelledby="must-title">
              <div className="section-heading"><div><span className="section-kicker">今晚必须完成</span><h2 id="must-title">{mustDo.length} 项 · {totalMinutes} 分钟</h2></div><strong className="section-total">按截止时间保护</strong></div>
              <InventoryTaskRows tasks={mustDo} />
            </section>
          ) : null}
          {completed.length ? (
            <section className="page-section" aria-labelledby="complete-title">
              <div className="section-heading"><div><span className="section-kicker green">已处理</span><h2 id="complete-title">已经完成</h2></div><CheckCircle2 className="green-icon" size={22} /></div>
              <InventoryTaskRows tasks={completed} />
            </section>
          ) : null}
          {optional.length ? (
            <section className="page-section" aria-labelledby="optional-title">
              <div className="section-heading"><div><span className="section-kicker">有余力可提前</span><h2 id="optional-title">提前安排</h2></div></div>
              <InventoryTaskRows tasks={optional} />
            </section>
          ) : null}
        </div>
        <aside className="overview-future-rail" aria-labelledby="future-title">
          <div className="section-heading"><div><span className="section-kicker">不会丢失</span><h2 id="future-title">后续已安排</h2></div><strong className="section-total">{futureTasks.length} 项</strong></div>
          {futureTasks.length ? <InventoryTaskRows tasks={futureTasks} /> : <p className="empty-copy">当前没有跨夜任务。</p>}
        </aside>
      </div>

      {currentSession.allowed_actions.includes("build_plan") ? (
        <div className="primary-actions">
          <button className="button primary" type="button" onClick={buildPlan} disabled={pending}>
            <Route size={19} />{pending ? "正在计算..." : "生成今晚路线"}
          </button>
        </div>
      ) : null}
    </main>
  );
}
