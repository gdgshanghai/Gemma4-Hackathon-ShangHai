'use client';

import React, { useCallback, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AIMissionGenerator } from '@/components/mission';
import { PixelBadge, PixelButton, PixelDialog } from '@/components/pixel';
import { ROUTES } from '@/constants';
import { Mission, MissionStatus } from '@/types';
import { useMissionStore } from '@/stores/missionStore';

interface CareerTaskBoardProps {
  missions: Mission[];
  careerId: string;
  isDemoMode?: boolean;
  onMissionGenerated?: (mission: Mission, source: 'api' | 'fallback') => void;
}

const COLUMNS: { status: MissionStatus; title: string; note: string }[] = [
  { status: MissionStatus.AVAILABLE, title: '待领取', note: 'AI 主管发布的新委托' },
  { status: MissionStatus.ACCEPTED, title: '进行中', note: '正在产出交付物' },
  { status: MissionStatus.SUBMITTED, title: '评审中', note: '等待 AI 同事反馈' },
  { status: MissionStatus.COMPLETED, title: '已完成', note: '可沉淀到作品集' },
];

function normalizeMissionStatus(status: MissionStatus | string | undefined): MissionStatus {
  if (status === MissionStatus.LOCKED) return MissionStatus.LOCKED;
  if (status === MissionStatus.ACCEPTED) return MissionStatus.ACCEPTED;
  if (status === MissionStatus.SUBMITTED) return MissionStatus.SUBMITTED;
  if (status === MissionStatus.COMPLETED) return MissionStatus.COMPLETED;
  return MissionStatus.AVAILABLE;
}

export default function CareerTaskBoard({ missions, careerId, isDemoMode = false, onMissionGenerated }: CareerTaskBoardProps) {
  const [selectedMission, setSelectedMission] = useState<Mission | null>(null);
  const [isGeneratorOpen, setIsGeneratorOpen] = useState(false);
  const router = useRouter();
  const { getMissionStatus, acceptMission } = useMissionStore();

  const groupedMissions = useMemo(() => {
    const groups: Record<MissionStatus, { mission: Mission; currentStatus: MissionStatus }[]> = {
      [MissionStatus.AVAILABLE]: [],
      [MissionStatus.ACCEPTED]: [],
      [MissionStatus.SUBMITTED]: [],
      [MissionStatus.COMPLETED]: [],
      [MissionStatus.LOCKED]: [],
    };

    missions.forEach((mission) => {
      const currentStatus = normalizeMissionStatus(getMissionStatus(mission.id, mission.status));
      groups[currentStatus].push({ mission, currentStatus });
    });

    return groups;
  }, [missions, getMissionStatus]);

  const handleButtonClick = useCallback(
    (mission: Mission, currentStatus: MissionStatus) => {
      if (currentStatus === MissionStatus.LOCKED) return;
      const demoParam = isDemoMode ? '?demo=1' : '';

      if (currentStatus === MissionStatus.AVAILABLE) {
        acceptMission(mission.id);
        router.push(ROUTES.MISSION(mission.id) + demoParam);
        return;
      }

      if (currentStatus === MissionStatus.ACCEPTED) {
        router.push(ROUTES.MISSION_SUBMIT(mission.id) + demoParam);
        return;
      }

      if (currentStatus === MissionStatus.SUBMITTED || currentStatus === MissionStatus.COMPLETED) {
        router.push(ROUTES.MISSION_FEEDBACK(mission.id) + demoParam);
      }
    },
    [acceptMission, router, isDemoMode],
  );

  const handleGeneratedMissionAccepted = useCallback(
    (mission: Mission, source: 'api' | 'fallback') => {
      acceptMission(mission.id);
      onMissionGenerated?.(mission, source);
    },
    [acceptMission, onMissionGenerated],
  );

  const lockedMissions = groupedMissions[MissionStatus.LOCKED];

  if (missions.length === 0) {
    return (
      <section id="career-task-board" className="border-2 border-slate-700 bg-slate-950/86 p-6 backdrop-blur-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="mb-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
              Route Preview
            </div>
            <h2 className="pixel-title text-2xl font-bold text-amber-300">路线建设中</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
              这座职业岛已经完成视觉和故事设定，任务卡正在扩展。你可以先生成一张 AI 委托，
              或回到数据山脉体验完整闭环。
            </p>
          </div>
          <PixelButton onClick={() => setIsGeneratorOpen(true)}>生成一张委托</PixelButton>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {['了解岗位日常', '拆解一项真实需求', '沉淀为作品集证据'].map((item, index) => (
            <div key={item} className="border-2 border-slate-700 bg-slate-900/60 p-4">
              <p className="font-mono text-xs text-amber-300">0{index + 1}</p>
              <p className="mt-2 font-bold text-slate-100">{item}</p>
            </div>
          ))}
        </div>

        <AIMissionGenerator
          open={isGeneratorOpen}
          onClose={() => setIsGeneratorOpen(false)}
          careerId={careerId}
          onMissionAccepted={handleGeneratedMissionAccepted}
        />
      </section>
    );
  }

  return (
    <>
      <section id="career-task-board" className="space-y-5">
        <div className="border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="mb-2 font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">
                Real Work Orders
              </div>
              <h2 className="pixel-title text-2xl font-bold text-amber-300">真实委托板</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                任务板只保留状态和下一步动作；故事感由职业岛背景和导师反馈承载。
              </p>
            </div>
            <PixelButton onClick={() => setIsGeneratorOpen(true)}>生成新委托</PixelButton>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.map((column) => (
            <TaskColumn
              key={column.status}
              title={column.title}
              note={column.note}
              items={groupedMissions[column.status]}
              onSelect={setSelectedMission}
              onAction={handleButtonClick}
            />
          ))}
        </div>

        {lockedMissions.length > 0 ? (
          <div className="border-2 border-slate-700 bg-slate-950/82 p-5 backdrop-blur-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-300">未解锁的远方任务</h3>
              <PixelBadge variant="neutral">{lockedMissions.length} 个</PixelBadge>
            </div>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {lockedMissions.map(({ mission }) => (
                <div key={mission.id} className="border border-slate-700 bg-slate-900/56 p-4 opacity-70">
                  <h4 className="mb-2 font-bold text-slate-400">{mission.title}</h4>
                  <p className="text-xs leading-5 text-slate-500">完成前置试炼后解锁。</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {selectedMission ? (
        <MissionDetailDialog
          mission={selectedMission}
          status={getMissionStatus(selectedMission.id, selectedMission.status)}
          onClose={() => setSelectedMission(null)}
          onAction={handleButtonClick}
        />
      ) : null}

      <AIMissionGenerator
        open={isGeneratorOpen}
        onClose={() => setIsGeneratorOpen(false)}
        careerId={careerId}
        onMissionAccepted={handleGeneratedMissionAccepted}
      />
    </>
  );
}

function TaskColumn({
  title,
  note,
  items,
  onSelect,
  onAction,
}: {
  title: string;
  note: string;
  items: { mission: Mission; currentStatus: MissionStatus }[];
  onSelect: (mission: Mission) => void;
  onAction: (mission: Mission, status: MissionStatus) => void;
}) {
  return (
    <div className="min-w-0 border-2 border-slate-700 bg-slate-950/84 p-4 backdrop-blur-sm">
      <div className="mb-4 border-b border-slate-700 pb-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-bold text-amber-300">{title}</h3>
          <span className="border border-slate-600 px-2 py-1 font-mono text-xs text-slate-300">{items.length}</span>
        </div>
        <p className="mt-1 text-xs leading-5 text-slate-500">{note}</p>
      </div>

      <div className="space-y-3">
        {items.length === 0 ? (
          <div className="border border-dashed border-slate-700 bg-slate-900/36 p-5 text-center text-xs text-slate-500">
            暂无委托
          </div>
        ) : (
          items.map(({ mission, currentStatus }) => (
            <MissionCard
              key={mission.id}
              mission={mission}
              status={currentStatus}
              onSelect={() => onSelect(mission)}
              onAction={() => onAction(mission, currentStatus)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function MissionCard({
  mission,
  status,
  onSelect,
  onAction,
}: {
  mission: Mission;
  status: MissionStatus;
  onSelect: () => void;
  onAction: () => void;
}) {
  const safeRewardExp = mission.rewardExp ?? 0;
  const safeDifficulty = mission.difficulty ?? 'medium';

  return (
    <article
      onClick={onSelect}
      className="group cursor-pointer border border-slate-700 bg-slate-900/74 p-3 transition hover:-translate-y-0.5 hover:border-amber-500 hover:bg-slate-900/90"
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <h4 className="line-clamp-2 text-sm font-bold leading-5 text-slate-100">{mission.title}</h4>
        <PixelBadge variant={status === MissionStatus.COMPLETED ? 'success' : 'warning'} className="shrink-0 text-xs">
          {statusLabel(status)}
        </PixelBadge>
      </div>
      <p className="mb-3 line-clamp-3 text-xs leading-5 text-slate-400">{mission.description}</p>
      <div className="mb-3 flex flex-wrap gap-2">
        <span className="border border-amber-700/70 px-2 py-1 text-xs text-amber-200">+{safeRewardExp} XP</span>
        <span className="border border-slate-600 px-2 py-1 text-xs text-slate-300">{difficultyLabel(safeDifficulty)}</span>
      </div>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onAction();
        }}
        className="w-full border border-amber-700 bg-amber-500 px-3 py-2 text-xs font-bold text-black transition group-hover:bg-amber-400"
      >
        {actionLabel(status)}
      </button>
    </article>
  );
}

function MissionDetailDialog({
  mission,
  status,
  onClose,
  onAction,
}: {
  mission: Mission;
  status: MissionStatus;
  onClose: () => void;
  onAction: (mission: Mission, status: MissionStatus) => void;
}) {
  const safeRewardExp = mission.rewardExp ?? 0;
  const safeDifficulty = mission.difficulty ?? 'medium';
  const safeObjectives = mission.objectives ?? [];
  const safeDeliverables = mission.deliverables ?? [];
  const safeCriteria = mission.criteria ?? [];
  const safeBackground = mission.background ?? mission.description ?? '暂无背景描述';

  return (
    <PixelDialog open onClose={onClose} title={mission.title}>
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <PixelBadge variant="warning">+{safeRewardExp} XP</PixelBadge>
          <PixelBadge variant="neutral">{difficultyLabel(safeDifficulty)}</PixelBadge>
          <PixelBadge variant={status === MissionStatus.COMPLETED ? 'success' : 'neutral'}>{statusLabel(status)}</PixelBadge>
        </div>

        <DetailBlock title="任务背景" items={[safeBackground]} />
        <DetailBlock title="任务目标" items={safeObjectives} />
        <DetailBlock title="交付物" items={safeDeliverables} />
        <DetailBlock title="AI 同事评审标准" items={safeCriteria} />

        <div className="flex justify-end gap-3 pt-2">
          <PixelButton variant="secondary" onClick={onClose}>
            关闭
          </PixelButton>
          {status !== MissionStatus.LOCKED ? (
            <PixelButton onClick={() => onAction(mission, status)}>{actionLabel(status)}</PixelButton>
          ) : null}
        </div>
      </div>
    </PixelDialog>
  );
}

function DetailBlock({ title, items }: { title: string; items: string[] | undefined }) {
  const safeItems = items ?? [];
  return (
    <section className="border border-slate-700 bg-slate-900/70 p-4">
      <h4 className="mb-2 font-bold text-amber-300">{title}</h4>
      <ul className="space-y-2">
        {(safeItems.length > 0 ? safeItems : ['暂无内容']).map((item, index) => (
          <li key={`${title}-${index}`} className="flex gap-2 text-sm leading-6 text-slate-300">
            <span className="mt-2 h-2 w-2 shrink-0 bg-amber-400" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function statusLabel(status: MissionStatus) {
  if (status === MissionStatus.AVAILABLE) return '待领取';
  if (status === MissionStatus.ACCEPTED) return '进行中';
  if (status === MissionStatus.SUBMITTED) return '评审中';
  if (status === MissionStatus.COMPLETED) return '已完成';
  return '未解锁';
}

function actionLabel(status: MissionStatus) {
  if (status === MissionStatus.AVAILABLE) return '接受委托';
  if (status === MissionStatus.ACCEPTED) return '继续提交';
  if (status === MissionStatus.SUBMITTED) return '查看评审';
  if (status === MissionStatus.COMPLETED) return '查看报告';
  return '未解锁';
}

function difficultyLabel(difficulty: Mission['difficulty']) {
  if (difficulty === 'easy') return '入门';
  if (difficulty === 'medium') return '进阶';
  return '高阶';
}
