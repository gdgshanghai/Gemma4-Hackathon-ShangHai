import { Check, RotateCcw, X } from "lucide-react";
import { useState } from "react";

import type { EveningResponse } from "../api/contracts";

const STEPS = [
  { label: "今晚盘点", hint: "把作业说清" },
  { label: "今晚全貌", hint: "看见全部任务" },
  { label: "我的路线", hint: "确定今晚顺序" },
  { label: "睡前复盘", hint: "只说没完成" },
] as const;

function activeStep(session: EveningResponse | undefined, reviewOpen: boolean): number {
  if (!session) return 0;
  if (reviewOpen || session.stage === "closed") return 3;
  if (session.stage === "plan_draft" || session.stage === "committed") return 2;
  if (session.stage === "inventory_confirmed" || session.stage === "capacity_conflict") return 1;
  return 0;
}

export function AppHeader({
  session,
  reviewOpen,
  notice,
  demoMode = false,
  demoOutdated = false,
  onResetDemo,
  onDismissNotice,
}: {
  session: EveningResponse | undefined;
  reviewOpen: boolean;
  notice: string | null;
  demoMode?: boolean;
  demoOutdated?: boolean;
  onResetDemo?: () => Promise<void>;
  onDismissNotice: () => void;
}) {
  const current = activeStep(session, reviewOpen);
  const [resetting, setResetting] = useState(false);

  async function resetDemo() {
    if (!onResetDemo || !window.confirm("确认重开今日演示？当前演示记录会保留为只读。")) return;
    setResetting(true);
    try {
      await onResetDemo();
    } finally {
      setResetting(false);
    }
  }

  return (
    <>
      <header className="app-header">
        <div className="header-inner">
          <div className="brand-row">
            <div className="brand-mark" aria-hidden="true">S</div>
            <div>
              <strong>时间规划小助手</strong>
              <span>先看清今晚，再一步步完成</span>
            </div>
          </div>
          <ol className="step-nav" aria-label="今晚进度">
            {STEPS.map((step, index) => (
              <li key={step.label} className={index === current ? "active" : index < current ? "done" : ""}>
                <span className="step-dot" aria-hidden="true">
                  {index < current ? <Check size={14} strokeWidth={3} /> : index + 1}
                </span>
                <span className="step-copy"><strong>{step.label}</strong><small>{step.hint}</small></span>
              </li>
            ))}
          </ol>
          {demoMode ? (
            <div className="demo-controls">
              <span className="demo-badge">演示模式</span>
              <button className="button demo-reset" type="button" disabled={resetting} onClick={() => void resetDemo()}>
                <RotateCcw size={16} />{resetting ? "正在重开" : "重开今日演示"}
              </button>
            </div>
          ) : null}
        </div>
      </header>
      {demoMode && demoOutdated ? (
        <div className="demo-script-warning" role="status">
          <strong>演示脚本已更新，请重开今日演示</strong>
          <span>旧会话和技术 trace 会保留为只读，不会被删除。</span>
        </div>
      ) : null}
      {notice ? (
        <div className="notice-wrap" role="status">
          <div className="notice">
            <span>{notice}</span>
            <button className="icon-button compact" type="button" onClick={onDismissNotice} aria-label="关闭提示" title="关闭提示">
              <X size={18} />
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
