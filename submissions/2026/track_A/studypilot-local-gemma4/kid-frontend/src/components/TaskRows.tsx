import { CheckCircle2, CircleDashed, Clock3 } from "lucide-react";

import type { CompletionState, IntakeDraftTask, InventoryTask } from "../api/contracts";

const COMPLETION_LABELS: Record<CompletionState, string> = {
  pending: "待完成",
  partial: "完成一部分",
  completed: "已完成",
  uncertain: "待确认",
  no_task: "无需完成",
};

const SOURCE_LABELS: Record<InventoryTask["estimate_source"], string> = {
  history_p80: "近期保守用时",
  parent_range: "家庭基线校准",
  child_adjusted: "按你的估时调整",
  domain_default: "七年级参考基线",
};

const CONFIDENCE_LABELS: Record<InventoryTask["estimate_confidence"], string> = {
  high: "高把握",
  medium: "中等把握",
  low: "低把握",
};

const SUBJECT_LABELS: Record<string, string> = {
  mathematics: "数学",
  math: "数学",
  chinese: "语文",
  english: "英语",
  civics: "道德与法治",
  history: "历史",
  geography: "地理",
  biology: "生物",
};

function subjectLabel(subject: string | null): string | null {
  if (!subject) return null;
  return SUBJECT_LABELS[subject.toLowerCase()] ?? subject;
}

function plannedDateLabel(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const weekday = weekdays[
    new Date(Date.UTC(year ?? 0, (month ?? 1) - 1, day ?? 1)).getUTCDay()
  ];
  return `${weekday} · ${value}`;
}

export function CompletionBadge({ state }: { state: CompletionState }) {
  const completed = state === "completed" || state === "no_task";
  return (
    <span className={`status-badge ${completed ? "completed" : "pending"}`}>
      {completed ? <CheckCircle2 size={15} /> : <CircleDashed size={15} />}
      {COMPLETION_LABELS[state]}
    </span>
  );
}

export function DraftTaskRows({ tasks }: { tasks: IntakeDraftTask[] }) {
  return (
    <div className="task-rows">
      {tasks.map((task, index) => (
        <div className="task-row" key={`${task.title}-${index}`}>
          <span className="task-subject-mark">{subjectLabel(task.subject) ?? "其他"}</span>
          <div className="task-main">
            <div className="task-title-line">
              <strong>{task.title}</strong>
            </div>
            <div className="task-meta">
              <CompletionBadge state={task.completion_state} />
              {task.child_estimate_minutes !== null ? <span><Clock3 size={14} />你估计 {task.child_estimate_minutes} 分钟</span> : null}
              {task.deadline_text ? <span>截止：{task.deadline_text}</span> : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function InventoryTaskRows({ tasks }: { tasks: InventoryTask[] }) {
  return (
    <div className="task-rows">
      {tasks.map((task) => (
        <div className="task-row inventory-row" key={task.id}>
          <span className="task-subject-mark">{subjectLabel(task.subject) ?? "其他"}</span>
          <div className="task-main">
            <div className="task-title-line">
              <strong>{task.title}</strong>
              <span className="task-duration"><Clock3 size={16} />{task.conservative_minutes} 分钟</span>
            </div>
            <div className="task-meta">
              <CompletionBadge state={task.completion_state} />
              {task.deadline_text ? <span>截止：{task.deadline_text}</span> : null}
              {task.planned_evening_date ? <span>暂排：{plannedDateLabel(task.planned_evening_date)}</span> : null}
            </div>
            <div className="estimate-note">
              <span>来源：{SOURCE_LABELS[task.estimate_source]}</span>
              <span>可信度：{CONFIDENCE_LABELS[task.estimate_confidence]}</span>
            </div>
            {(task.estimate_breakdown ?? []).length > 0 ? (
              <details className="estimate-breakdown">
                <summary>估时依据</summary>
                <ul>
                  {(task.estimate_breakdown ?? []).map((item) => (
                    <li key={`${task.id}-${item.component}`}>
                      <span>{item.label}</span>
                      <strong>{item.reference_minutes} → {item.calibrated_minutes} 分钟</strong>
                      {item.remaining_quantity !== null && item.unit ? (
                        <small>剩余 {item.remaining_quantity}{item.unit}</small>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}

export function completionLabel(state: CompletionState): string {
  return COMPLETION_LABELS[state];
}
