import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, Clock3, MoonStar, RotateCw, TimerReset } from "lucide-react";

import { getLatestEvening } from "../api/client";
import { formatCalendarDate, localDateValue } from "../date";
import { eveningRecordStatus } from "../workspace";

const stageLabels: Record<string, string> = {
  created: "等待盘点",
  intake_draft: "正在盘点",
  coverage_pending: "正在核对",
  inventory_confirmed: "清单已确认",
  plan_draft: "路线待确认",
  committed: "正在执行",
  closed: "已归档",
  capacity_conflict: "正在调整容量",
  needs_confirmation: "等待确认",
  model_unavailable: "整理服务暂不可用",
};

function formatClock(value: string | null | undefined): string {
  if (!value) return "--:--";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function ResultView() {
  const [sessionDate, setSessionDate] = useState(localDateValue);
  const resultQuery = useQuery({
    queryKey: ["evening-result", sessionDate],
    queryFn: () => getLatestEvening(sessionDate),
    enabled: /^\d{4}-\d{2}-\d{2}$/.test(sessionDate),
  });
  const result = resultQuery.data;
  const plan = result?.data.plan;
  const outcomes = new Map(result?.data.outcomes.map((item) => [item.task_id, item]) ?? []);
  const completedCount = result?.data.outcomes.filter((item) => item.completion_state === "completed").length ?? 0;
  const unfinishedCount = result?.data.outcomes.length ? result.data.outcomes.length - completedCount : 0;
  const recordStatus = result
    ? eveningRecordStatus(result.stage, result.session_date, localDateValue())
    : null;
  const recordStatusLabel = {
    archived: "已归档",
    incomplete: "当晚未完成",
    in_progress: "进行中",
  }[recordStatus ?? "in_progress"];

  return (
    <main className="page-shell result-page">
      <div className="page-heading compact-heading">
        <div>
          <span className="eyebrow"><MoonStar size={15} /> 家庭工作台</span>
          <h1>晚间记录</h1>
          <p>{formatCalendarDate(sessionDate)}</p>
        </div>
        <label className="date-field">
          <span>日期</span>
          <input type="date" value={sessionDate} onChange={(event) => setSessionDate(event.target.value)} />
        </label>
      </div>

      {resultQuery.isPending ? (
        <section className="center-state"><Clock3 size={26} /><strong>正在读取今晚状态</strong></section>
      ) : resultQuery.isError ? (
        <section className="center-state">
          <strong>暂时无法读取晚间记录</strong>
          <button className="button secondary" type="button" onClick={() => void resultQuery.refetch()}>
            <RotateCw size={17} />重新连接
          </button>
        </section>
      ) : !result ? (
        <section className="empty-result">
          <MoonStar size={30} />
          <div><strong>这一天还没有晚间计划</strong><p>孩子开始盘点后，这里会显示只读进度。</p></div>
        </section>
      ) : (
        <>
          <section className="result-workspace" aria-label="晚间记录状态">
            <div className="result-status-summary">
              <span className="section-kicker">当前状态</span>
              <strong>{stageLabels[result.stage]}</strong>
              <small>{recordStatusLabel} · {formatCalendarDate(result.session_date)} · v{result.version}</small>
            </div>
            <div className="result-metrics">
              <div><Clock3 size={19} /><span>预计结束</span><b>{formatClock(plan?.predicted_finish_at)}</b></div>
              <div><TimerReset size={19} /><span>真实余量</span><b>{plan ? `${plan.true_surplus_minutes} 分钟` : "--"}</b></div>
              <div><CheckCircle2 size={19} /><span>已完成</span><b>{result.stage === "closed" ? `${completedCount} 项` : "进行中"}</b></div>
              <div><MoonStar size={19} /><span>未完成</span><b>{result.stage === "closed" ? `${unfinishedCount} 项` : "--"}</b></div>
            </div>
          </section>

          <section className="page-section" aria-labelledby="result-tasks-title">
            <div className="section-heading">
              <div><span className="section-kicker">只读清单</span><h2 id="result-tasks-title">任务结果</h2></div>
              <span className="revision-label">{result.data.inventory.length} 项</span>
            </div>
            <div className="parent-task-list">
              {result.data.inventory.map((task) => {
                const outcome = outcomes.get(task.id);
                return (
                  <div className="parent-task-row" key={task.id}>
                    <span><strong>{task.title}</strong><small>{task.subject ?? "其他"} · 保守 {task.conservative_minutes} 分钟</small></span>
                    <span className={`result-status ${outcome?.completion_state === "completed" ? "done" : "pending"}`}>
                      {outcome ? (outcome.completion_state === "completed" ? "已完成" : "未完成") : "计划中"}
                      {outcome?.actual_minutes ? ` · 实际 ${outcome.actual_minutes} 分钟` : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}
    </main>
  );
}
