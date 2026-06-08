'use client';

import React, { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PixelButton, PixelDialog, PixelTextarea } from '@/components/pixel';
import { ROUTES } from '@/constants';
import { getCareerMentor } from '@/data';
import { useCommunityStore } from '@/stores/communityStore';

interface EngineerMailboxDialogProps {
  open: boolean;
  onClose: () => void;
  careerId: string;
}

const tagPresets: Record<string, string[]> = {
  'software-engineer': ['环境配置', '问题复现', '联调排查', '测试失败'],
  'data-analyst': ['指标口径', 'SQL', '分层分析', '报告表达'],
  'product-designer': ['需求拆解', '用户旅程', '原型说明', '优先级'],
  'ai-researcher': ['实验设计', '模型评测', '提示工程', '研究复盘'],
};

export default function EngineerMailboxDialog({ open, onClose, careerId }: EngineerMailboxDialogProps) {
  const router = useRouter();
  const mentor = useMemo(() => getCareerMentor(careerId), [careerId]);
  const { displayName, setDisplayName, publishIssue } = useCommunityStore();
  const [name, setName] = useState(displayName);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [priority, setPriority] = useState<'normal' | 'high'>('normal');

  const tags = tagPresets[careerId] || tagPresets['software-engineer'];
  const canPublish = title.trim().length >= 6 && content.trim().length >= 30;

  const toggleTag = (tag: string) => {
    setSelectedTags((current) =>
      current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag].slice(0, 5),
    );
  };

  const handlePublish = () => {
    if (!canPublish) return;
    setDisplayName(name);
    const issue = publishIssue({
      careerId,
      title,
      content,
      tags: selectedTags.length > 0 ? selectedTags : ['人工协助'],
      priority,
    });
    setTitle('');
    setContent('');
    setSelectedTags([]);
    onClose();
    router.push(`${ROUTES.COMMUNITY}?career=${careerId}&issue=${issue.id}`);
  };

  return (
    <PixelDialog open={open} onClose={onClose} title="工程师信箱">
      <div className="space-y-4">
        <div className="border-2 border-slate-700 bg-slate-950 p-4">
          <div className="font-mono text-xs uppercase text-emerald-300">Human Escalation</div>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            这里不会让 AI 直接代答。问题会作为社区工单发布，由工程师、导师和同学基于真实经验继续讨论。
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {mentor.name}建议写清：发生背景、复现步骤、已经尝试过什么，以及希望大家帮你判断什么。
          </p>
        </div>

        <label className="block">
          <span className="mb-2 block text-xs text-slate-400">社区昵称</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full border-2 border-slate-600 bg-slate-900 p-3 font-mono text-sm text-slate-100 outline-none focus:border-amber-500"
            maxLength={16}
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-xs text-slate-400">问题标题</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：本地运行正常，提交评审后出现问题"
            className="w-full border-2 border-slate-600 bg-slate-900 p-3 font-mono text-sm text-slate-100 outline-none focus:border-amber-500"
            maxLength={56}
          />
        </label>

        <PixelTextarea
          value={content}
          onChange={setContent}
          placeholder="描述背景、复现步骤、已经尝试过的办法，以及希望工程师协助判断的部分。"
          rows={6}
        />

        <div>
          <div className="mb-2 text-xs text-slate-400">问题标签</div>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => toggleTag(tag)}
                className={`border px-3 py-2 text-xs ${
                  selectedTags.includes(tag)
                    ? 'border-amber-500 bg-amber-500 text-slate-950'
                    : 'border-slate-700 bg-slate-900 text-slate-300 hover:border-amber-600'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-700 pt-4">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={priority === 'high'}
              onChange={(event) => setPriority(event.target.checked ? 'high' : 'normal')}
              className="h-4 w-4 accent-amber-500"
            />
            需要优先协助
          </label>
          <div className="flex gap-3">
            <PixelButton variant="secondary" onClick={onClose}>取消</PixelButton>
            <PixelButton onClick={handlePublish} disabled={!canPublish}>发布到社区</PixelButton>
          </div>
        </div>
      </div>
    </PixelDialog>
  );
}
