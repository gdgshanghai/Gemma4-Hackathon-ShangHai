import { useMemo, useState } from "react";
import { Check, ClipboardCheck, Gauge, MoonStar } from "lucide-react";

import { closeEvening } from "../api/client";
import { completionLabel, CompletionBadge } from "../components/TaskRows";
import { useSession } from "../state/session";

export function ReviewView() {
  const { session, acceptResponse, handleActionError } = useSession();
  const [unfinished, setUnfinished] = useState<Set<string>>(new Set());
  const [deviationTaskId, setDeviationTaskId] = useState("");
  const [actualMinutes, setActualMinutes] = useState("");
  const [pending, setPending] = useState(false);

  const scheduledTasks = useMemo(() => {
    if (!session?.data.plan) return [];
    const inventory = new Map(session.data.inventory.map((task) => [task.id, task]));
    return session.data.plan.ordered_task_ids.flatMap((id) => {
      const task = inventory.get(id);
      return task ? [task] : [];
    });
  }, [session]);

  if (!session) return null;
  const currentSession = session;

  function toggle(taskId: string) {
    setUnfinished((current) => {
      const next = new Set(current);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  async function close() {
    setPending(true);
    try {
      acceptResponse(await closeEvening(
        currentSession.session_id,
        currentSession.version,
        [...unfinished],
        deviationTaskId && Number(actualMinutes) > 0
          ? { task_id: deviationTaskId, actual_minutes: Number(actualMinutes) }
          : null,
        null,
      ));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  if (currentSession.stage === "closed") {
    const outcomeByTask = new Map(currentSession.data.outcomes.map((outcome) => [outcome.task_id, outcome]));
    const unfinishedCount = currentSession.data.outcomes.filter((outcome) => outcome.completion_state !== "completed").length;
    const notes = [...new Set(currentSession.data.outcomes.flatMap((outcome) => outcome.note ? [outcome.note] : []))];
    return (
      <main className="page-shell">
        <div className="page-heading">
          <span className="eyebrow"><ClipboardCheck size={17} />睡前复盘</span>
          <h1>{unfinishedCount === 0 ? "今晚全部完成" : "今晚已经记下"}</h1>
          <p>{currentSession.planning_date} · 已归档</p>
        </div>
        <div className={`completion-summary ${unfinishedCount === 0 ? "all-done" : "has-unfinished"}`}>
          {unfinishedCount === 0 ? <Check size={24} /> : <MoonStar size={24} />}
          <div><strong>{unfinishedCount === 0 ? "全部完成" : `${unfinishedCount} 项未完成`}</strong><span>{unfinishedCount === 0 ? "今晚的计划已经收好。" : "未完成项没有消失，明天可以继续处理。"}</span></div>
        </div>
        <section className="page-section" aria-labelledby="result-title">
          <div className="section-heading"><div><span className="section-kicker">只读结果</span><h2 id="result-title">任务结果</h2></div></div>
          <div className="task-rows">
            {scheduledTasks.map((task) => {
              const outcome = outcomeByTask.get(task.id);
              return (
                <div className="task-row review-result-row" key={task.id}>
                  <div className="task-title-line"><strong>{task.title}</strong>{outcome ? <CompletionBadge state={outcome.completion_state} /> : <span>{completionLabel(task.completion_state)}</span>}</div>
                  {outcome?.actual_minutes ? <div className="estimate-note">记录实际用时 {outcome.actual_minutes} 分钟</div> : null}
                </div>
              );
            })}
          </div>
          {notes.length ? <div className="review-note"><strong>今晚备注</strong><p>{notes.join("；")}</p></div> : null}
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <div className="page-heading">
        <span className="eyebrow"><MoonStar size={17} />睡前复盘</span>
        <h1>今晚哪些还没完成？</h1>
        <p>只勾选没有完成的任务。</p>
      </div>
      <section className="page-section review-exception-section" aria-labelledby="unfinished-title" aria-label="未完成例外">
        <div className="section-heading"><div><span className="section-kicker">未完成检查</span><h2 id="unfinished-title">今晚路线里的任务</h2></div></div>
        <div className="checkbox-list">
          {scheduledTasks.map((task) => (
            <label key={task.id}>
              <input type="checkbox" checked={unfinished.has(task.id)} onChange={() => toggle(task.id)} />
              <span>{task.title}</span>
            </label>
          ))}
        </div>
        <div className={`selection-result ${unfinished.size === 0 ? "complete" : "unfinished"}`} role="status">
          {unfinished.size === 0 ? <><Check size={19} /><strong>没有勾选未完成项：全部完成</strong></> : <><MoonStar size={19} /><strong>已选 {unfinished.size} 项未完成</strong></>}
        </div>
      </section>
      <section className="page-section deviation-section" aria-labelledby="deviation-title">
        <div className="section-heading">
          <div><span className="section-kicker">可选，只记一项</span><h2 id="deviation-title">哪项和预计差得最多？</h2></div>
          <Gauge size={21} />
        </div>
        <div className="field-grid deviation-fields">
          <label>
            <span>任务</span>
            <select name="deviation-task" value={deviationTaskId} onChange={(event) => {
              setDeviationTaskId(event.target.value);
              if (!event.target.value) setActualMinutes("");
            }}>
              <option value="">今晚没有明显偏差</option>
              {scheduledTasks.map((task) => <option value={task.id} key={task.id}>{task.title}</option>)}
            </select>
          </label>
          <label>
            <span>大约实际用了多久</span>
            <div className="input-suffix">
              <input
                name="actual-minutes"
                type="number"
                min="1"
                max="720"
                step="1"
                disabled={!deviationTaskId}
                value={actualMinutes}
                onChange={(event) => setActualMinutes(event.target.value)}
              />
              <span>分钟</span>
            </div>
          </label>
        </div>
      </section>
      <div className="primary-actions">
        <button className="button primary" type="button" onClick={close} disabled={pending || Boolean(deviationTaskId && Number(actualMinutes) < 1)}>
          <ClipboardCheck size={19} />{pending ? "正在保存..." : "保存睡前复盘"}
        </button>
      </div>
    </main>
  );
}
