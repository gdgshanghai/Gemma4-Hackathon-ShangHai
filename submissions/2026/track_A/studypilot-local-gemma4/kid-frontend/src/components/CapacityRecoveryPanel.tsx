import { useState } from "react";
import { AlertTriangle, Check, ClockArrowDown, Gauge } from "lucide-react";

import type { CapacityRecovery, InventoryTask } from "../api/contracts";


export function CapacityRecoveryPanel({
  recovery,
  tasks,
  pending,
  onStartEarlier,
  onAcceptFocus,
  onManualChoice,
}: {
  recovery: CapacityRecovery;
  tasks: InventoryTask[];
  pending: boolean;
  onStartEarlier: () => void;
  onAcceptFocus: () => void;
  onManualChoice: (taskIds: string[]) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const taskById = new Map(tasks.map((task) => [task.id, task]));
  const clock = recovery.recommended_start_time.slice(0, 5);

  function toggle(taskId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  if (recovery.mode === "start_earlier") {
    return (
      <section className="capacity-recovery" aria-labelledby="capacity-title">
        <div className="recovery-heading">
          <ClockArrowDown size={24} />
          <div>
            <span className="section-kicker warning">先把开始时间提前</span>
            <strong id="capacity-title">还差 {recovery.baseline_shortfall_minutes} 分钟</strong>
            <p>不减少明日任务，也不推迟结束时间。</p>
          </div>
        </div>
        <div className="recovery-action">
          <strong>今晚从 {clock} 开始</strong>
          <span>22:20结束学习，22:30睡眠不变</span>
          <button className="button primary" type="button" disabled={pending} onClick={onStartEarlier}>
            <Check size={18} />采用这个开始时间
          </button>
        </div>
      </section>
    );
  }

  if (recovery.mode === "focus_pace") {
    return (
      <section className="capacity-recovery" aria-labelledby="capacity-title">
        <div className="recovery-heading">
          <Gauge size={24} />
          <div>
            <span className="section-kicker warning">采用专注目标</span>
            <strong id="capacity-title">需要提速 {recovery.speedup_percent}%</strong>
            <p>只压缩今晚执行节奏，最高不超过 20%；保守估时不会被改写。</p>
          </div>
        </div>
        <div className="pace-target-list">
          {recovery.pace_targets.map((target) => (
            <div key={target.task_id}>
              <strong>{taskById.get(target.task_id)?.title ?? "今晚任务"}</strong>
              <span>保守 {target.conservative_minutes} 分钟</span>
              <b>今晚目标 {target.target_minutes} 分钟</b>
            </div>
          ))}
        </div>
        <div className="recovery-footer">
          <span>18:45最早开始，22:20结束学习，22:30睡眠不变</span>
          <button className="button primary" type="button" disabled={pending} onClick={onAcceptFocus}>
            <Gauge size={18} />采用专注路线
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="capacity-recovery manual-recovery" aria-labelledby="capacity-title">
      <div className="recovery-heading">
        <AlertTriangle size={24} />
        <div>
          <span className="section-kicker warning">已到系统规划极限</span>
          <strong id="capacity-title">最高提速后仍差 {recovery.residual_shortfall_minutes} 分钟</strong>
          <p>系统不会替你选择牺牲哪个明日任务。请自行选择今晚暂不安排的内容。</p>
        </div>
      </div>
      <div className="manual-risk-list">
        {tasks.map((task) => (
          <label key={task.id}>
            <input type="checkbox" checked={selected.has(task.id)} onChange={() => toggle(task.id)} />
            <span><strong>{task.title}</strong><small>明日截止风险 · 保守 {task.conservative_minutes} 分钟</small></span>
          </label>
        ))}
      </div>
      <div className="recovery-footer">
        <span>没有任务被默认勾选；22:30睡眠不变</span>
        <button
          className="button primary"
          type="button"
          disabled={pending || selected.size === 0}
          onClick={() => onManualChoice([...selected])}
        >
          <Check size={18} />按我的选择重算
        </button>
      </div>
    </section>
  );
}
