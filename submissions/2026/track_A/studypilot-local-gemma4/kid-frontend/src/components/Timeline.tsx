import { Coffee, ListChecks, Pause, Pin } from "lucide-react";

import type { EveningPlan, PlanBlock } from "../api/contracts";

const BLOCK_META: Record<PlanBlock["block_type"], { label: string; Icon: typeof ListChecks }> = {
  task: { label: "任务", Icon: ListChecks },
  fixed: { label: "固定安排", Icon: Pin },
  buffer: { label: "缓冲", Icon: Pause },
  break: { label: "休息", Icon: Coffee },
};

export function formatClock(value: string | null): string {
  if (!value) return "--:--";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Shanghai",
  }).format(new Date(value));
}

export function Timeline({ plan }: { plan: EveningPlan }) {
  const blocks = [...plan.blocks].sort((a, b) => a.ordinal - b.ordinal);
  return (
    <div className="timeline" aria-label="今晚时间路线">
      {blocks.map((block) => {
        const { label, Icon } = BLOCK_META[block.block_type];
        return (
          <div className={`timeline-row ${block.block_type}`} key={block.id}>
            <time className="timeline-time" dateTime={block.starts_at}>{formatClock(block.starts_at)}</time>
            <div className="timeline-track" aria-hidden="true"><span /></div>
            <div className="timeline-row-layout">
              <div className="timeline-title-group">
                <div className="timeline-label"><Icon size={16} /><span>{label}</span></div>
                <strong>{block.label}</strong>
              </div>
              <span className="timeline-window">{formatClock(block.starts_at)} - {formatClock(block.ends_at)}</span>
              <strong className="timeline-duration">
                {Math.max(0, Math.round((new Date(block.ends_at).getTime() - new Date(block.starts_at).getTime()) / 60000))} 分钟
              </strong>
            </div>
          </div>
        );
      })}
    </div>
  );
}
