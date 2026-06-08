import React, { useMemo, useState } from 'react';
import { getSkillStatus, SkillNodeStatus } from '@/components/skill/SkillNodeCard';
import { PixelBadge, PixelButton, PixelDialog, PixelProgress } from '@/components/pixel';
import { SkillNode } from '@/types';

interface CareerSkillTreeProps {
  skills: SkillNode[];
}

export default function CareerSkillTree({ skills }: CareerSkillTreeProps) {
  const [selectedSkill, setSelectedSkill] = useState<SkillNode | null>(null);

  const stats = useMemo(() => {
    const unlocked = skills.filter((skill) => skill.unlocked ?? false).length;
    const learning = skills.filter((skill) => getSkillStatus(skill) === 'learning').length;
    const mastered = skills.filter((skill) => getSkillStatus(skill) === 'mastered').length;
    const progress = skills.length > 0 ? Math.round((mastered / skills.length) * 100) : 0;
    return { unlocked, learning, mastered, progress };
  }, [skills]);

  const levels = useMemo(() => {
    const groups = new Map<number, SkillNode[]>();
    skills.forEach((skill) => {
      const level = skill.y ?? 0;
      groups.set(level, [...(groups.get(level) ?? []), skill]);
    });
    return Array.from(groups.entries())
      .sort(([a], [b]) => a - b)
      .map(([level, items]) => ({ 
        level, 
        items: items.sort((a, b) => (a.x ?? 0) - (b.x ?? 0)) 
      }));
  }, [skills]);

  if (skills.length === 0) {
    return (
      <section className="overflow-hidden border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
        <div className="mb-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
          Skill Constellation
        </div>
        <h2 className="pixel-title text-2xl font-bold text-amber-300">技能星图</h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          这条路线的技能节点正在扩展中。先完成一张任务卡，系统会把能力点沉淀到这里。
        </p>
      </section>
    );
  }

  return (
    <>
      <section className="overflow-hidden border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
              Skill Constellation
            </div>
            <h2 className="pixel-title text-2xl font-bold text-amber-300">技能星图</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              每个节点都应该绑定到一次真实任务。完成提交后，它会成为作品集里的能力证据。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <PixelBadge variant="success">已解锁 {stats.unlocked}</PixelBadge>
            <PixelBadge variant="warning">精通 {stats.mastered}</PixelBadge>
          </div>
        </div>

        <div className="mb-6 border border-slate-700 bg-slate-950/58 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-bold text-slate-300">总体掌握度</span>
            <span className="font-mono text-lg font-bold text-amber-300">{stats.progress}%</span>
          </div>
          <PixelProgress value={stats.progress} color="#f59e0b" />
          <div className="mt-3 text-xs text-slate-500">学习中 {stats.learning} 个节点</div>
        </div>

        <div className="relative space-y-9">
          {levels.map((group, groupIndex) => (
            <div key={group.level} className="relative">
              <div className="mb-3 flex items-center gap-3">
                <div className="h-px flex-1 bg-slate-700" />
                <span className="font-mono text-xs uppercase tracking-[0.16em] text-slate-400">
                  Layer {groupIndex + 1}
                </span>
                <div className="h-px flex-1 bg-slate-700" />
              </div>
              <div className="flex flex-wrap justify-center gap-4">
                {group.items.map((skill) => (
                  <SkillCrystal key={skill.id} skill={skill} onClick={() => setSelectedSkill(skill)} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {selectedSkill ? <SkillDetailDialog skill={selectedSkill} onClose={() => setSelectedSkill(null)} /> : null}
    </>
  );
}

function SkillCrystal({ skill, onClick }: { skill: SkillNode; onClick: () => void }) {
  const status = getSkillStatus(skill);
  const color = statusColor(status);
  const progress = skill.expToNext > 0 ? Math.min(100, Math.round((skill.exp / skill.expToNext) * 100)) : 0;
  const locked = status === 'locked';

  // 防止除以零或 NaN
  const safeLevel = skill.level ?? 0;
  const safeMaxLevel = skill.maxLevel ?? 1;

  return (
    <button
      type="button"
      onClick={locked ? undefined : onClick}
      className={`relative min-h-[142px] w-44 border-2 bg-slate-950/72 p-4 text-left transition ${
        locked ? 'cursor-not-allowed opacity-50 grayscale' : 'hover:-translate-y-0.5 hover:border-amber-400'
      }`}
      style={{ borderColor: color }}
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="h-7 w-7 rotate-45 border-2" style={{ borderColor: color, backgroundColor: `${color}22` }} />
        <span className="font-mono text-xs font-bold" style={{ color }}>
          Lv.{safeLevel}/{safeMaxLevel}
        </span>
      </div>
      <h3 className="mb-2 line-clamp-2 min-h-[40px] text-sm font-bold leading-5 text-slate-100">{skill.name}</h3>
      <p className="mb-3 line-clamp-2 text-xs leading-5 text-slate-500">{skill.description}</p>
      {locked ? (
        <div className="text-xs text-slate-500">完成前置节点解锁</div>
      ) : (
        <PixelProgress value={progress} color={color} height="h-2" />
      )}
    </button>
  );
}

function SkillDetailDialog({ skill, onClose }: { skill: SkillNode; onClose: () => void }) {
  const status = getSkillStatus(skill);
  const color = statusColor(status);
  const safeExp = skill.exp ?? 0;
  const safeExpToNext = skill.expToNext ?? 1;
  const progress = safeExpToNext > 0 ? Math.min(100, Math.round((safeExp / safeExpToNext) * 100)) : 0;

  return (
    <PixelDialog open onClose={onClose} title={skill.name}>
      <div className="space-y-5">
        <div className="text-center">
          <div className="mx-auto mb-3 h-12 w-12 rotate-45 border-4" style={{ borderColor: color, backgroundColor: `${color}22` }} />
          <PixelBadge variant={status === 'mastered' ? 'success' : status === 'learning' ? 'warning' : 'neutral'}>
            {statusText(status)}
          </PixelBadge>
        </div>

        <div className="border border-slate-700 bg-slate-900/70 p-4">
          <p className="text-sm leading-6 text-slate-300">{skill.description}</p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">经验进度</span>
            <span className="font-mono text-slate-200">{safeExp} / {safeExpToNext} XP</span>
          </div>
          <PixelProgress value={progress} color={color} />
        </div>

        <div className="border border-amber-700/60 bg-amber-950/20 p-4">
          <div className="mb-1 font-bold text-amber-300">导师提示</div>
          <p className="text-sm leading-6 text-amber-100/80">
            把这个技能绑定到一次真实委托里练习，完成提交后更容易形成作品集证据。
          </p>
        </div>

        <PixelButton variant="secondary" onClick={onClose} fullWidth>关闭</PixelButton>
      </div>
    </PixelDialog>
  );
}

function statusColor(status: SkillNodeStatus) {
  if (status === 'locked') return '#64748b';
  if (status === 'available') return '#38bdf8';
  if (status === 'learning') return '#f59e0b';
  return '#10b981';
}

function statusText(status: SkillNodeStatus) {
  if (status === 'locked') return '未解锁';
  if (status === 'available') return '可学习';
  if (status === 'learning') return '学习中';
  return '已精通';
}
