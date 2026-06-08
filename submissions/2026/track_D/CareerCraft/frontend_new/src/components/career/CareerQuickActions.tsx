import React from 'react';
import { useRouter } from 'next/navigation';
import { ROUTES } from '@/constants';

interface CareerQuickActionsProps {
  onScrollToTasks?: () => void;
  onScrollToSkills?: () => void;
  onAskMentor?: () => void;
}

const quickActions = [
  { id: 'tasks', index: '01', title: '领取委托', description: '进入任务看板，开始一次真实岗位模拟。', action: 'tasks' },
  { id: 'skills', index: '02', title: '技能路线', description: '查看当前任务应该沉淀哪些能力证据。', action: 'skills' },
  { id: 'mailbox', index: '03', title: '工程师信箱', description: '把 AI 无法替代的经验问题发布到社区讨论。', action: 'mailbox' },
  { id: 'portfolio', index: '04', title: '成长档案馆', description: '查看任务成果、评审记录和作品集证据。', action: 'portfolio' },
];

export default function CareerQuickActions({ onScrollToTasks, onScrollToSkills, onAskMentor }: CareerQuickActionsProps) {
  const router = useRouter();

  const handleAction = (action: string) => {
    if (action === 'tasks') onScrollToTasks?.();
    if (action === 'skills') onScrollToSkills?.();
    if (action === 'mailbox') onAskMentor?.();
    if (action === 'portfolio') router.push(ROUTES.PORTFOLIO);
  };

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
      {quickActions.map((action) => (
        <button
          key={action.id}
          type="button"
          onClick={() => handleAction(action.action)}
          className="group border-2 border-slate-700 bg-slate-950/82 p-4 text-left backdrop-blur-sm transition hover:-translate-y-0.5 hover:border-amber-500 hover:bg-slate-900/90"
        >
          <div className="mb-3 flex items-center justify-between">
            <span className="font-mono text-xs uppercase text-slate-500">Action</span>
            <span className="font-mono text-sm font-bold text-amber-300">{action.index}</span>
          </div>
          <h4 className="mb-2 text-base font-bold text-slate-100">{action.title}</h4>
          <p className="text-sm leading-6 text-slate-400">{action.description}</p>
        </button>
      ))}
    </div>
  );
}
