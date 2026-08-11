import { useEffect, useState } from "react";
import { Clock3, RefreshCw } from "lucide-react";

import { updateTimeBoundary } from "../api/client";
import { useSession } from "../state/session";

function clockMinutes(value: string): number {
  const [hours = 0, minutes = 0] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

export function TimeBoundaryEditor() {
  const { session, acceptResponse, handleActionError } = useSession();
  const [startTime, setStartTime] = useState("");
  const [sleepTime, setSleepTime] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!session) return;
    setStartTime(session.data.time_boundary.start_time.slice(0, 5));
    setSleepTime(session.data.time_boundary.sleep_time.slice(0, 5));
  }, [session?.session_id, session?.data.time_boundary.start_time, session?.data.time_boundary.sleep_time]);

  if (!session || session.stage === "committed" || session.stage === "closed") return null;
  const minutes = clockMinutes(sleepTime) - clockMinutes(startTime);
  const validWindow = startTime >= "18:45" && sleepTime <= "22:20" && minutes > 0;

  async function update() {
    if (!session || !validWindow) return;
    setPending(true);
    try {
      acceptResponse(await updateTimeBoundary(
        session.session_id,
        session.version,
        `${startTime}:00`,
        `${sleepTime}:00`,
      ));
    } catch (error) {
      await handleActionError(error);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="time-boundary-editor" aria-label="调整今晚时间边界">
      <div className="time-boundary-intro">
        <span>时间边界</span>
        <strong>路线提交前可调整</strong>
      </div>
      <div className="time-boundary-fields">
        <label><span>今晚开始安排</span><input type="time" min="18:45" value={startTime} onChange={(event) => setStartTime(event.target.value)} /></label>
        <label><span>今晚学习结束</span><input type="time" max="22:20" value={sleepTime} onChange={(event) => setSleepTime(event.target.value)} /></label>
      </div>
      <div className="time-boundary-result"><Clock3 size={18} /><span>总窗口</span><strong>{Math.max(minutes, 0)} 分钟</strong></div>
      <small className="time-boundary-note">学习结束后留给睡前准备，22:30按时睡觉。</small>
      <button className="button secondary" type="button" disabled={pending || !validWindow} onClick={() => void update()}>
        <RefreshCw size={18} />{pending ? "正在更新..." : "更新时间边界"}
      </button>
    </section>
  );
}
