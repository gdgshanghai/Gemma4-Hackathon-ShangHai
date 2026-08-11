import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Check, Clock3, Save, ShieldCheck, SunMedium } from "lucide-react";

import { commitPlan, createPlan } from "../api/client";
import { formatClock, Timeline } from "../components/Timeline";
import { TimeBoundaryEditor } from "../components/TimeBoundaryEditor";
import { InventoryTaskRows } from "../components/TaskRows";
import { useSession } from "../state/session";

export function RouteView({ onOpenReview }: { onOpenReview: () => void }) {
  const { session, acceptResponse, handleActionError } = useSession();
  const plan = session?.data.plan;
  const [order, setOrder] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setOrder(plan?.ordered_task_ids ?? []);
  }, [plan?.id, plan?.ordered_task_ids]);

  const inventoryById = useMemo(
    () => new Map(session?.data.inventory.map((task) => [task.id, task]) ?? []),
    [session?.data.inventory],
  );

  if (!session || !plan) return null;
  const currentSession = session;
  const currentPlan = plan;
  const canReorder = currentSession.allowed_actions.includes("reorder_plan");
  const canCommit = currentSession.allowed_actions.includes("commit_plan");
  const changed = order.some((id, index) => id !== currentPlan.ordered_task_ids[index]);
  const firstTask = inventoryById.get(order[0] ?? currentPlan.ordered_task_ids[0] ?? "");
  const paceTargetById = new Map(currentPlan.pace_targets.map((target) => [target.task_id, target]));
  const firstPaceTarget = firstTask ? paceTargetById.get(firstTask.id) : undefined;
  const futureTasks = currentSession.data.inventory.filter(
    (task) => task.planning_bucket === "future_scheduled",
  );

  function move(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= order.length) return;
    setOrder((current) => {
      const next = [...current];
      const item = next[index];
      if (!item) return current;
      next.splice(index, 1);
      next.splice(target, 0, item);
      return next;
    });
  }

  async function saveOrder() {
    setPending(true);
    try {
      acceptResponse(await createPlan(currentSession.session_id, currentSession.version, "child_reorder", order));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  async function commit() {
    setPending(true);
    try {
      acceptResponse(await commitPlan(currentSession.session_id, currentPlan.id, currentSession.version));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="page-shell">
      <div className="page-heading route-heading">
        <span className="eyebrow"><ShieldCheck size={17} />我的路线</span>
        <h1>{currentPlan.committed ? "今晚就按这条路线走" : "路线已经排好"}</h1>
        <p>{currentPlan.committed ? "路线已确认，按自己的节奏完成即可。" : "确认前可以调整一次任务顺序。"}</p>
      </div>

      {canCommit ? <TimeBoundaryEditor /> : null}

      <section className="route-command" aria-label="计划结果">
        <div className="finish-panel">
          <span><Clock3 size={18} />预计结束</span>
          <strong>{formatClock(currentPlan.predicted_finish_at)}</strong>
          <small>学习结束时间不后移</small>
        </div>
        <div className="first-action-panel">
          <span>第一步</span>
          <strong>{firstTask?.title ?? "按路线开始"}</strong>
          <small>{firstTask ? (
            firstPaceTarget
              ? `保守 ${firstTask.conservative_minutes} 分钟 / 今晚目标 ${firstPaceTarget.target_minutes} 分钟`
              : `保守 ${firstTask.conservative_minutes} 分钟`
          ) : "先完成路线第一项"}</small>
        </div>
        <div className="route-metrics">
          <div><ShieldCheck size={18} /><span>预留缓冲</span><b>{currentPlan.capacity.buffer_minutes} 分钟</b></div>
          <div><SunMedium size={18} /><span>提前安排</span><b>{currentPlan.scheduled_optional_minutes} 分钟</b></div>
          <div className="surplus"><Check size={18} /><span>真实余量</span><b>{currentPlan.true_surplus_minutes} 分钟</b></div>
        </div>
      </section>

      {currentPlan.pace_targets.length ? (
        <section className="focus-route-summary" aria-labelledby="focus-route-title">
          <div>
            <span className="section-kicker">今晚专注节奏</span>
            <h2 id="focus-route-title">专注目标不改写家庭基线</h2>
          </div>
          <div className="focus-target-grid">
            {currentPlan.pace_targets.map((target) => (
              <div key={target.task_id}>
                <strong>{inventoryById.get(target.task_id)?.title ?? "今晚任务"}</strong>
                <span>保守 {target.conservative_minutes} 分钟</span>
                <b>今晚目标 {target.target_minutes} 分钟</b>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {canReorder ? (
        <section className="page-section" aria-labelledby="order-title">
          <div className="section-heading"><div><span className="section-kicker">确认前可调整一次</span><h2 id="order-title">任务顺序</h2></div></div>
          <ol className="reorder-list">
            {order.map((taskId, index) => {
              const task = inventoryById.get(taskId);
              return (
                <li key={taskId}>
                  <span className="order-number">{index + 1}</span>
                  <span className="reorder-title">{task?.title ?? "未命名任务"}</span>
                  <div className="reorder-controls">
                    <button className="icon-button" type="button" onClick={() => move(index, -1)} disabled={index === 0 || pending} aria-label={`上移${task?.title ?? "任务"}`} title="上移">
                      <ArrowUp size={19} />
                    </button>
                    <button className="icon-button" type="button" onClick={() => move(index, 1)} disabled={index === order.length - 1 || pending} aria-label={`下移${task?.title ?? "任务"}`} title="下移">
                      <ArrowDown size={19} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ol>
          <div className="secondary-action-row">
            <button className="button secondary" type="button" onClick={saveOrder} disabled={!changed || pending}>
              <Save size={18} />保存这个顺序
            </button>
          </div>
        </section>
      ) : null}

      <section className="page-section" aria-labelledby="timeline-title">
        <div className="section-heading"><div><span className="section-kicker">时间不会漂移</span><h2 id="timeline-title">今晚时间线</h2></div></div>
        <Timeline plan={currentPlan} />
      </section>

      {futureTasks.length ? (
        <section className="page-section" aria-labelledby="future-route-title">
          <div className="section-heading"><div><span className="section-kicker">路线之外仍有位置</span><h2 id="future-route-title">后续已安排</h2></div></div>
          <InventoryTaskRows tasks={futureTasks} />
        </section>
      ) : null}

      <div className="primary-actions">
        {canCommit ? (
          <button className="button primary" type="button" onClick={commit} disabled={pending}>
            <Check size={19} />{pending ? "正在确认..." : "确认这条路线"}
          </button>
        ) : null}
        {currentPlan.committed && currentSession.allowed_actions.includes("close_evening") ? (
          <button className="button primary" type="button" onClick={onOpenReview}>
            <SunMedium size={19} />睡前复盘
          </button>
        ) : null}
      </div>
    </main>
  );
}
