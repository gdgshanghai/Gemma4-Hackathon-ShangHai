import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ClipboardList, Clock3, Send } from "lucide-react";

import {
  addIntakeTurn,
  confirmInventory,
  createEvening,
  getDemoScenario,
  resetDemoEvening,
} from "../api/client";
import { DraftTaskRows } from "../components/TaskRows";
import { useSession } from "../state/session";

export function IntakeView() {
  const { session, acceptResponse, handleActionError } = useSession();
  const [startTime, setStartTime] = useState("19:30");
  const [sleepTime, setSleepTime] = useState("22:20");
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [demoPresetLoaded, setDemoPresetLoaded] = useState(false);
  const demoMode = import.meta.env.VITE_DEMO_MODE === "true";
  const demoQuery = useQuery({
    queryKey: ["demo", "scenario"],
    queryFn: getDemoScenario,
    enabled: demoMode,
    staleTime: Number.POSITIVE_INFINITY,
  });

  function loadDemoHomework() {
    const scenario = demoQuery.data;
    if (!scenario) return;
    setText(scenario.child_report_text);
    setDemoPresetLoaded(true);
  }

  function loadDemoScenario() {
    const scenario = demoQuery.data;
    if (!scenario) return;
    setStartTime(scenario.start_time.slice(0, 5));
    setSleepTime(scenario.sleep_time.slice(0, 5));
    loadDemoHomework();
  }

  async function bootstrap(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    try {
      const response = demoMode
        ? await resetDemoEvening(null)
        : await createEvening({
            start_time: `${startTime}:00`,
            sleep_time: `${sleepTime}:00`,
          });
      acceptResponse(response);
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  async function submitIntake(event: FormEvent) {
    event.preventDefault();
    if (!session || !text.trim()) return;
    setPending(true);
    try {
      const response = await addIntakeTurn(session.session_id, session.version, text.trim());
      acceptResponse(response);
      setText("");
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  async function confirm() {
    if (!session) return;
    setPending(true);
    try {
      acceptResponse(await confirmInventory(session.session_id, session.version));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  const [startHour = 0, startMinute = 0] = startTime.split(":").map(Number);
  const [sleepHour = 0, sleepMinute = 0] = sleepTime.split(":").map(Number);
  const windowMinutes = sleepHour * 60 + sleepMinute - startHour * 60 - startMinute;
  const validWindow = startTime >= "18:45" && sleepTime <= "22:20" && windowMinutes > 0;

  if (!session) {
    return (
      <main className="page-shell bootstrap-page">
        <div className="page-heading">
          <span className="eyebrow"><ClipboardList size={17} />今晚盘点</span>
          <h1>先确定今晚的时间边界</h1>
          <p>任务只安排在这段学习时间内，结束后留给睡前准备。</p>
        </div>
        <div className="command-grid intake-command-grid">
          <form className="command-workspace form-section" onSubmit={bootstrap}>
            {demoMode && demoQuery.data ? (
              <div className="preset-row">
                <button className="button secondary" type="button" onClick={loadDemoScenario}>
                  载入演示情景
                </button>
                <span className="preset-note">模拟日期：{demoQuery.data.planning_date} 星期一</span>
                {demoPresetLoaded ? <span className="preset-note">模拟数据，尚未保存</span> : null}
              </div>
            ) : null}
            <div className="field-grid">
              <label>
                <span>今晚开始安排</span>
                <input type="time" min="18:45" value={startTime} onChange={(event) => setStartTime(event.target.value)} required />
              </label>
              <label>
                <span>今晚学习结束</span>
                <input type="time" max="22:20" value={sleepTime} onChange={(event) => setSleepTime(event.target.value)} required />
              </label>
            </div>
            <div className="time-window-summary"><Clock3 size={19} /><span>系统自动计算</span><strong>可安排 {Math.max(windowMinutes, 0)} 分钟</strong></div>
            <div className="primary-actions">
              <button className="button primary" type="submit" disabled={pending || !validWindow}>
                <ClipboardList size={19} />{pending ? "正在开始..." : "开始今晚盘点"}
              </button>
            </div>
          </form>
          <aside className="context-rail" aria-label="今晚已知边界">
            <div className="context-section"><span>学习窗口</span><strong>{startTime} - {sleepTime}</strong><small>{Math.max(windowMinutes, 0)} 分钟</small></div>
            <div className="context-section"><span>学校作业单</span><strong>如有学校文本会自动对照</strong><small>遗漏项目会补进清单</small></div>
            <div className="context-section"><span>今晚底线</span><strong>22:20 停止学习</strong><small>之后留给睡前准备，22:30按时睡觉</small></div>
          </aside>
        </div>
      </main>
    );
  }

  const draft = session.data.intake_draft;
  const canConfirm = session.allowed_actions.includes("confirm_inventory") && Boolean(draft);
  const canIntake = session.allowed_actions.some((action) => action === "describe_homework" || action === "add_intake_turn");
  return (
    <main className="page-shell">
      <div className="page-heading">
        <span className="eyebrow"><ClipboardList size={17} />今晚盘点</span>
        <h1>{draft ? "看看清单是否完整" : "把今晚的作业一次说清楚"}</h1>
        <p>{demoMode && demoQuery.data ? `模拟日期：${demoQuery.data.planning_date} 星期一` : "依据你提供的清单"}</p>
      </div>

      {session.stage === "model_unavailable" ? (
        <div className="attention-callout" role="alert">
          <strong>输入已经保存</strong>
          <span>整理服务暂时不可用，可以保留原话后重试。</span>
        </div>
      ) : null}

      {draft?.coverage_notes.length ? (
        <div className="attention-callout" role="status">
          <strong>学校作业单对照</strong>
          {draft.coverage_notes.map((note) => <span key={note}>{note}</span>)}
          <span>遗漏项目已经加入清单，你只需补充完成状态或剩余情况。</span>
        </div>
      ) : null}

      <div className="command-grid intake-command-grid">
        <div className="command-workspace">
          {draft ? (
            <section className="page-section" aria-labelledby="draft-title">
              <div className="section-heading">
                <div><span className="section-kicker">共 {draft.tasks.length} 项</span><h2 id="draft-title">整理后的清单</h2></div>
              </div>
              <DraftTaskRows tasks={draft.tasks} />
            </section>
          ) : null}

          {canIntake ? (
            <form className="page-section intake-form" onSubmit={submitIntake}>
              {demoMode && demoQuery.data ? (
                <div className="preset-row">
                  <button className="button secondary" type="button" onClick={loadDemoHomework}>
                    一键代入预设作业
                  </button>
                  {demoPresetLoaded ? <span className="preset-note">模拟数据，尚未保存</span> : null}
                </div>
              ) : null}
              <label htmlFor="homework-text">{draft ? "只补充遗漏或更正即可" : "今晚有哪些作业？哪些已经完成？"}</label>
              <textarea
                id="homework-text"
                value={text}
                onChange={(event) => setText(event.target.value)}
                maxLength={10000}
                rows={5}
                placeholder="例如：数学练习册还有两页，大约 30 分钟；英语课文已经在学校背完了；语文作文还没写。"
              />
              <div className="secondary-action-row">
                <button className="button secondary" type="submit" disabled={pending || !text.trim()}>
                  <Send size={18} />{session.stage === "model_unavailable" ? "重试整理" : draft ? "应用补充" : "整理清单"}
                </button>
              </div>
            </form>
          ) : null}

          {canConfirm ? (
            <div className="primary-actions">
              <button className="button primary" type="button" onClick={confirm} disabled={pending}>
                <Check size={19} />{pending ? "正在确认..." : "清单完整，确认今晚任务"}
              </button>
            </div>
          ) : null}
        </div>
        <aside className="context-rail" aria-label="今晚已知边界">
          <div className="context-section"><span>学习窗口</span><strong>{session.data.time_boundary.start_time.slice(0, 5)} - {session.data.time_boundary.sleep_time.slice(0, 5)}</strong><small>净可安排 {session.data.time_boundary.net_minutes} 分钟</small></div>
          <div className="context-section"><span>学校作业单</span><strong>{session.data.coverage_mode === "school_verified" ? "已经完成对照" : "等待清单确认"}</strong><small>只补充遗漏或完成状态</small></div>
          <div className="context-section"><span>学习结束线</span><strong>结束时间不后移</strong><small>路线提交前仍可调整开始时间</small></div>
        </aside>
      </div>
    </main>
  );
}
