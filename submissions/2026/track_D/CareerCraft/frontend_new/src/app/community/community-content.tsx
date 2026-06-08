'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { EngineerMailboxDialog } from '@/components/community';
import { BackButton } from '@/components/common';
import { AppShell, ScenePage } from '@/components/layout';
import { PixelBadge, PixelButton, PixelTextarea } from '@/components/pixel';
import { IMAGES } from '@/constants/images';
import { careerIslands } from '@/data';
import { useCommunityStore } from '@/stores/communityStore';
import { EngineerIssue, EngineerIssueStatus } from '@/types';

const statusLabels: Record<EngineerIssueStatus, string> = {
  open: '待讨论',
  triaged: '已受理',
  solved: '已解决',
};

export default function CommunityContent() {
  const searchParams = useSearchParams();
  const careerFromUrl = searchParams.get('career') || 'all';
  const issueFromUrl = searchParams.get('issue') || '';
  const [activeCareerId, setActiveCareerId] = useState(careerFromUrl);
  const [selectedIssueId, setSelectedIssueId] = useState(issueFromUrl);
  const [showMine, setShowMine] = useState(false);
  const [mailboxOpen, setMailboxOpen] = useState(false);
  const [reply, setReply] = useState('');
  const {
    issues,
    userId,
    displayName,
    setDisplayName,
    addReply,
    markReplyHelpful,
    updateIssueStatus,
  } = useCommunityStore();

  const filteredIssues = useMemo(
    () =>
      issues
        .filter((issue) => activeCareerId === 'all' || issue.careerId === activeCareerId)
        .filter((issue) => !showMine || issue.authorId === userId)
        .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)),
    [activeCareerId, issues, showMine, userId],
  );

  const selectedIssue = useMemo(
    () => issues.find((issue) => issue.id === selectedIssueId) || filteredIssues[0],
    [filteredIssues, issues, selectedIssueId],
  );

  useEffect(() => {
    if (issueFromUrl) setSelectedIssueId(issueFromUrl);
  }, [issueFromUrl]);

  const handleReply = () => {
    if (!selectedIssue || !reply.trim()) return;
    addReply(selectedIssue.id, reply);
    setReply('');
  };

  const activePublishCareer = activeCareerId === 'all' ? 'software-engineer' : activeCareerId;

  return (
    <AppShell>
      <ScenePage backgroundImage={IMAGES.GUILD_HALL} maxWidth="7xl" position="center center">
        <div className="space-y-5 py-8">
          <section
            className="relative min-h-[330px] overflow-hidden border-4 border-slate-700 bg-slate-950"
            style={{
              backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.97) 0%, rgba(2,6,23,0.82) 48%, rgba(2,6,23,0.2) 100%), url(${IMAGES.ENGINEER_COMMUNITY_GUILD})`,
              backgroundPosition: 'center',
              backgroundSize: 'cover',
            }}
          >
            <div className="relative z-10 flex min-h-[330px] flex-col justify-between gap-8 p-6 md:p-8">
              <BackButton fallbackHref="/lobby" label="返回职业世界" className="self-start" />
              <div className="flex flex-wrap items-end justify-between gap-5">
                <div className="max-w-2xl">
                  <PixelBadge variant="warning">Engineer Exchange</PixelBadge>
                  <h1 className="pixel-title mt-4 text-3xl text-amber-300 md:text-5xl">工程师交流站</h1>
                  <p className="mt-4 text-sm leading-7 text-slate-300">
                    AI 适合帮助整理思路，真实经验适合处理环境差异、排查顺序、边界判断和职业选择。把问题写成清晰工单，再让讨论沉淀为可复用经验。
                  </p>
                </div>
                <PixelButton onClick={() => setMailboxOpen(true)}>发布问题</PixelButton>
              </div>
            </div>
          </section>

          <section className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
            <aside className="space-y-4">
              <div className="border-2 border-slate-700 bg-slate-950/90 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="font-mono text-xs uppercase text-emerald-300">Channels</span>
                  <button
                    type="button"
                    onClick={() => setShowMine((value) => !value)}
                    className={`border px-2 py-1 text-xs ${showMine ? 'border-amber-500 bg-amber-500 text-slate-950' : 'border-slate-700 text-slate-400'}`}
                  >
                    我的问题
                  </button>
                </div>
                <div className="grid gap-2">
                  <ChannelButton label="全部问题" active={activeCareerId === 'all'} onClick={() => setActiveCareerId('all')} />
                  {careerIslands.map((career) => (
                    <ChannelButton
                      key={career.id}
                      label={career.name}
                      active={activeCareerId === career.id}
                      onClick={() => setActiveCareerId(career.id)}
                    />
                  ))}
                </div>
                <label className="mt-4 block border-t border-slate-800 pt-4">
                  <span className="mb-2 block text-xs text-slate-500">我的社区昵称</span>
                  <input
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    className="w-full border-2 border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-amber-500"
                    maxLength={16}
                  />
                </label>
              </div>

              <div className="max-h-[680px] space-y-3 overflow-y-auto border-2 border-slate-700 bg-slate-950/90 p-3">
                {filteredIssues.map((issue) => (
                  <IssueListItem
                    key={issue.id}
                    issue={issue}
                    selected={selectedIssue?.id === issue.id}
                    isMine={issue.authorId === userId}
                    onClick={() => setSelectedIssueId(issue.id)}
                  />
                ))}
                {filteredIssues.length === 0 ? (
                  <div className="border border-dashed border-slate-700 p-6 text-center text-sm text-slate-400">
                    当前频道还没有符合条件的问题。
                  </div>
                ) : null}
              </div>
            </aside>

            <main className="min-w-0">
              {selectedIssue ? (
                <IssueDetail
                  issue={selectedIssue}
                  canManage={selectedIssue.authorId === userId}
                  reply={reply}
                  onReplyChange={setReply}
                  onReply={handleReply}
                  onHelpful={(replyId) => markReplyHelpful(selectedIssue.id, replyId)}
                  onStatusChange={(status) => updateIssueStatus(selectedIssue.id, status)}
                />
              ) : (
                <div className="border-2 border-slate-700 bg-slate-950/90 p-10 text-center text-slate-300">
                  选择一个问题查看讨论，或发布你的第一封工程师信。
                </div>
              )}
            </main>
          </section>
        </div>

        <EngineerMailboxDialog
          open={mailboxOpen}
          onClose={() => setMailboxOpen(false)}
          careerId={activePublishCareer}
        />
      </ScenePage>
    </AppShell>
  );
}

function ChannelButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`border px-3 py-2 text-left text-sm transition ${
        active ? 'border-amber-500 bg-amber-500 text-slate-950' : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-amber-600'
      }`}
    >
      {label}
    </button>
  );
}

function IssueListItem({
  issue,
  selected,
  isMine,
  onClick,
}: {
  issue: EngineerIssue;
  selected: boolean;
  isMine: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full border p-3 text-left transition hover:-translate-y-0.5 ${
        selected ? 'border-amber-500 bg-amber-950/35' : 'border-slate-700 bg-slate-900/70 hover:border-amber-700'
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <PixelBadge variant={issue.status === 'solved' ? 'success' : 'neutral'}>{statusLabels[issue.status]}</PixelBadge>
        <span className="font-mono text-xs text-slate-500">{isMine ? '我的问题' : formatTime(issue.createdAt)}</span>
      </div>
      <h3 className="line-clamp-2 text-sm font-bold leading-5 text-slate-100">{issue.title}</h3>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-400">{issue.content}</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {issue.tags.slice(0, 3).map((tag) => <span key={tag} className="border border-slate-700 px-2 py-1 text-[11px] text-slate-400">{tag}</span>)}
      </div>
    </button>
  );
}

function IssueDetail({
  issue,
  canManage,
  reply,
  onReplyChange,
  onReply,
  onHelpful,
  onStatusChange,
}: {
  issue: EngineerIssue;
  canManage: boolean;
  reply: string;
  onReplyChange: (value: string) => void;
  onReply: () => void;
  onHelpful: (replyId: string) => void;
  onStatusChange: (status: EngineerIssueStatus) => void;
}) {
  const career = careerIslands.find((item) => item.id === issue.careerId);
  return (
    <article className="space-y-4">
      <div className="border-2 border-slate-700 bg-slate-950/90 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <PixelBadge variant="warning">{career?.name ?? issue.careerId}</PixelBadge>
            <PixelBadge variant={issue.priority === 'high' ? 'warning' : 'neutral'}>
              {issue.priority === 'high' ? '优先协助' : '普通问题'}
            </PixelBadge>
            <PixelBadge variant={issue.status === 'solved' ? 'success' : 'neutral'}>{statusLabels[issue.status]}</PixelBadge>
          </div>
          {canManage ? (
            <select
              value={issue.status}
              onChange={(event) => onStatusChange(event.target.value as EngineerIssueStatus)}
              className="border-2 border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"
            >
              <option value="open">待讨论</option>
              <option value="triaged">已受理</option>
              <option value="solved">已解决</option>
            </select>
          ) : null}
        </div>
        <h2 className="text-2xl font-bold leading-9 text-amber-300">{issue.title}</h2>
        <p className="mt-2 text-xs text-slate-500">{issue.authorName} / {formatTime(issue.createdAt)}</p>
        <p className="mt-5 whitespace-pre-wrap text-sm leading-7 text-slate-300">{issue.content}</p>
      </div>

      <div className="border-2 border-slate-700 bg-slate-950/90 p-5">
        <h3 className="mb-4 text-lg font-bold text-amber-300">讨论回复 · {issue.replies.length}</h3>
        <div className="space-y-3">
          {issue.replies.map((item) => (
            <div key={item.id} className="border border-slate-700 bg-slate-900/70 p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div><span className="font-bold text-slate-100">{item.authorName}</span><span className="ml-2 text-xs text-emerald-300">{item.authorRole}</span></div>
                <span className="font-mono text-xs text-slate-500">{formatTime(item.createdAt)}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{item.content}</p>
              <button type="button" onClick={() => onHelpful(item.id)} className="mt-3 text-xs text-amber-300 hover:text-amber-200">
                有帮助 · {item.helpfulCount}
              </button>
            </div>
          ))}
          {issue.replies.length === 0 ? <div className="border border-dashed border-slate-700 p-5 text-sm text-slate-500">暂无回复，补充复现步骤会更容易得到有效协助。</div> : null}
        </div>
      </div>

      <div className="border-2 border-amber-700/75 bg-slate-950/90 p-5">
        <h3 className="mb-3 text-lg font-bold text-amber-300">参与讨论</h3>
        <PixelTextarea value={reply} onChange={onReplyChange} rows={4} placeholder="写下排查建议、补充信息或复现结果。" />
        <div className="mt-3 flex justify-end"><PixelButton onClick={onReply} disabled={!reply.trim()}>回复</PixelButton></div>
      </div>
    </article>
  );
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '刚刚';
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}