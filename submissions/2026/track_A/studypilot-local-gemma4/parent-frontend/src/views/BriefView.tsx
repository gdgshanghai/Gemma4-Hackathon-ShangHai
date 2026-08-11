import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Check, FileText, LoaderCircle, RotateCw, Save } from "lucide-react";

import { ApiError, getDemoScenario, getSchoolBrief, saveSchoolBrief } from "../api/client";
import { formatCalendarDate, formatDateTime, localDateValue } from "../date";

type Notice = { tone: "success" | "warning" | "error"; text: string } | null;

export function BriefView() {
  const queryClient = useQueryClient();
  const [briefDate, setBriefDate] = useState(localDateValue);
  const [rawText, setRawText] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [demoPresetLoaded, setDemoPresetLoaded] = useState(false);
  const demoMode = import.meta.env.VITE_DEMO_MODE === "true";
  const demoQuery = useQuery({
    queryKey: ["demo", "scenario"],
    queryFn: getDemoScenario,
    enabled: demoMode,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const briefQuery = useQuery({
    queryKey: ["school-brief", briefDate],
    queryFn: () => getSchoolBrief(briefDate),
    enabled: /^\d{4}-\d{2}-\d{2}$/.test(briefDate),
  });
  const brief = briefQuery.data;

  useEffect(() => {
    setRawText("");
    setNotice(null);
  }, [briefDate]);

  useEffect(() => {
    if (brief?.brief_date === briefDate) setRawText(brief.raw_text);
  }, [brief, briefDate]);

  const saveMutation = useMutation({
    mutationFn: saveSchoolBrief,
    onSuccess: (envelope, input) => {
      queryClient.setQueryData(["school-brief", input.briefDate], envelope.data.record);
      setRawText(envelope.data.record.raw_text);
      setNotice({
        tone: "success",
        text: envelope.data.no_op ? "内容未变化，当前版本保持不变。" : `已保存第 ${envelope.data.revision} 版。`,
      });
    },
    onError: async (error, input) => {
      if (error instanceof ApiError && error.status === 409) {
        const latest = await queryClient.fetchQuery({
          queryKey: ["school-brief", input.briefDate],
          queryFn: () => getSchoolBrief(input.briefDate),
        });
        if (input.briefDate === briefDate) setRawText(latest?.raw_text ?? "");
        setNotice({ tone: "warning", text: "这一天已有更新，已载入最新版本，请确认后再保存。" });
        return;
      }
      setNotice({ tone: "error", text: "暂时无法保存作业单，请稍后重试。" });
    },
  });

  const baseline = brief === null ? null : (brief?.raw_text ?? "");
  const canSave = !saveMutation.isPending && !briefQuery.isPending && rawText !== baseline;

  function submit() {
    setNotice(null);
    saveMutation.mutate({
      briefDate,
      rawText,
      expectedRevision: brief?.revision ?? 0,
    });
  }

  return (
    <main className="page-shell">
      <div className="page-heading compact-heading">
        <div>
          <span className="eyebrow"><CalendarDays size={15} /> 家庭工作台</span>
          <h1>今日作业单</h1>
          <p>{formatCalendarDate(briefDate)}</p>
        </div>
        <label className="date-field">
          <span>日期</span>
          <input
            type="date"
            value={briefDate}
            disabled={saveMutation.isPending}
            onChange={(event) => setBriefDate(event.target.value)}
          />
        </label>
      </div>

      {notice && <div className={`notice ${notice.tone}`} role="status">{notice.text}</div>}

      {briefQuery.isError ? (
        <section className="center-state">
          <strong>暂时无法读取这一天的作业单</strong>
          <button className="button secondary" type="button" onClick={() => void briefQuery.refetch()}>
            <RotateCw size={17} /> 重新连接
          </button>
        </section>
      ) : (
        <div className="workspace-grid">
          <section className="form-section brief-copy-workspace" aria-label="学校原文" aria-busy={briefQuery.isPending}>
            <div className="section-heading">
              <div>
                <span className="section-kicker">学校原文</span>
                <h2>当天通知</h2>
              </div>
              {briefQuery.isPending && <LoaderCircle className="spin" size={20} aria-label="读取中" />}
            </div>
            {demoMode && demoQuery.data ? (
              <div className="preset-row">
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => {
                    setRawText(demoQuery.data.school_brief_text);
                    setDemoPresetLoaded(true);
                  }}
                >
                  载入示例作业单
                </button>
                {demoPresetLoaded ? <span className="preset-note">模拟数据，尚未保存</span> : null}
              </div>
            ) : null}
            <label className="textarea-field">
              <span className="sr-only">粘贴学校当天的作业通知</span>
              <textarea
                rows={13}
                maxLength={50_000}
                value={rawText}
                disabled={briefQuery.isPending || saveMutation.isPending}
                placeholder="粘贴老师或学校发布的当天作业；没有通知时可留空保存。"
                onChange={(event) => setRawText(event.target.value)}
              />
            </label>
            <div className="field-footer">
              <span>{rawText.length.toLocaleString("zh-CN")} / 50,000</span>
              <button className="button primary" type="button" disabled={!canSave} onClick={submit}>
                {saveMutation.isPending ? <LoaderCircle className="spin" size={18} /> : <Save size={18} />}
                保存作业单
              </button>
            </div>
          </section>

          <aside className="status-panel" aria-label="当前状态">
            <div className={`status-icon ${brief ? "saved" : "empty"}`}>
              {brief ? <Check size={20} /> : <FileText size={20} />}
            </div>
            <span className="section-kicker">当前状态</span>
            <strong>{brief ? (brief.raw_text.trim() ? "已保存" : "已记录无学校文本") : "尚未保存"}</strong>
            <dl>
              <div><dt>版本</dt><dd>{brief ? `第 ${brief.revision} 版` : "-"}</dd></div>
              <div><dt>保存时间</dt><dd>{brief ? formatDateTime(brief.created_at) : "-"}</dd></div>
              <div><dt>来源</dt><dd>{brief ? "家长粘贴" : "-"}</dd></div>
            </dl>
          </aside>
        </div>
      )}
    </main>
  );
}
