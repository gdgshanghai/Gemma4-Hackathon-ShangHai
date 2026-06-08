import React, { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import DemoHighlight from '@/components/demo/DemoHighlight';
import { PixelBadge, PixelButton, PixelDialog } from '@/components/pixel';
import { ROUTES } from '@/constants';
import { useMissionStore } from '@/stores/missionStore';
import { Mission, MissionStatus } from '@/types';
import { MVP_RAG_RESOURCES } from '@/utils/demoFlow';

interface MissionStartPanelProps {
  mission: Mission;
}

export default function MissionStartPanel({ mission }: MissionStartPanelProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemoMode = searchParams.get('demo') === '1';
  const demoStep = Number.parseInt(searchParams.get('step') || '1', 10);
  const isMvpMission = mission.id === 'community-activity-drop';
  const [ragDialogOpen, setRagDialogOpen] = useState(false);
  const { acceptMission, getMissionStatus } = useMissionStore();
  const currentStatus = getMissionStatus(mission.id, mission.status) || mission.status;

  const demoParam = isDemoMode ? '?demo=1' : '';

  const handleAction = () => {
    if (currentStatus === MissionStatus.AVAILABLE) {
      acceptMission(mission.id);
      router.push(ROUTES.MISSION_SUBMIT(mission.id) + (isDemoMode ? '?demo=1&step=6' : ''));
      return;
    }

    if (currentStatus === MissionStatus.ACCEPTED) {
      router.push(ROUTES.MISSION_SUBMIT(mission.id) + demoParam);
      return;
    }

    if (currentStatus === MissionStatus.SUBMITTED || currentStatus === MissionStatus.COMPLETED) {
      router.push(ROUTES.MISSION_FEEDBACK(mission.id) + demoParam);
    }
  };

  return (
    <>
      <section className="border-2 border-slate-700 bg-slate-950/90 p-5 backdrop-blur-sm">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">Control</div>
            <h2 className="mt-1 font-bold text-amber-300">任务控制台</h2>
          </div>
          <PixelBadge variant={currentStatus === MissionStatus.COMPLETED ? 'success' : currentStatus === MissionStatus.ACCEPTED ? 'warning' : 'neutral'}>
            {statusLabel(currentStatus)}
          </PixelBadge>
        </div>

        <div className="mb-4 border border-slate-700 bg-slate-900/60 p-4">
          <div className="mb-1 text-xs text-slate-500">推荐行动</div>
          <p className="text-sm leading-6 text-slate-300">{recommendedAction(currentStatus)}</p>
        </div>

        <div className="mb-4 flex items-center justify-between border border-slate-700 bg-slate-900/60 p-3 text-sm">
          <span className="text-slate-400">预计耗时</span>
          <span className="font-bold text-amber-300">20-40 分钟</span>
        </div>

        <DemoHighlight targetStep={3} currentStep={demoStep} label="推荐学习资源">
          <div className="mb-4 border border-slate-700 bg-slate-900/60 p-3">
            <div className="mb-2 text-xs font-bold text-slate-400">学习支援</div>
            <PixelButton fullWidth variant="secondary" onClick={() => setRagDialogOpen(true)}>
              RAG 知识库检索
            </PixelButton>
            <p className="mt-2 text-center text-xs text-slate-500">查找与任务相关的学习材料</p>
          </div>
        </DemoHighlight>

        <div className="mb-4 border border-amber-700/70 bg-amber-950/20 p-3">
          <p className="text-sm leading-6 text-amber-100/80">
            先读清楚任务，再开始提交。能讲清楚“为什么这样做”，比只给结果更重要。
          </p>
        </div>

        <div className="mb-4">
          <PixelButton
            fullWidth
            variant="secondary"
            onClick={() => router.push(`/feynman/${mission.id}${isDemoMode ? '?demo=1&step=4' : ''}`)}
          >
            先做费曼理解挑战
          </PixelButton>
        </div>

        <DemoHighlight targetStep={5} currentStep={demoStep} label="接受任务">
          <PixelButton fullWidth onClick={handleAction} disabled={currentStatus === MissionStatus.LOCKED}>
            {actionButtonText(currentStatus)}
          </PixelButton>
        </DemoHighlight>
      </section>

      <PixelDialog open={ragDialogOpen} onClose={() => setRagDialogOpen(false)} title="RAG 知识库检索">
        <div className="space-y-4">
          <p className="text-slate-300">以下是为这个任务推荐的学习资源：</p>
          <div className="space-y-3">
            {MVP_RAG_RESOURCES.map((resource) => (
              <div key={resource.id} className="border border-slate-700 bg-slate-900/70 p-4">
                <div className="mb-2 text-xs font-bold text-amber-300">{resource.category}</div>
                <h4 className="mb-1 font-bold text-slate-200">{resource.title}</h4>
                <p className="text-sm leading-6 text-slate-400">{resource.description}</p>
              </div>
            ))}
          </div>

          {isDemoMode && isMvpMission ? (
            <div className="border-t border-slate-700 pt-4">
              <PixelButton
                fullWidth
                onClick={() => {
                  setRagDialogOpen(false);
                  router.push(`/feynman/${mission.id}?demo=1&step=4`);
                }}
              >
                前往费曼挑战
              </PixelButton>
            </div>
          ) : null}
        </div>
      </PixelDialog>
    </>
  );
}

function statusLabel(status: MissionStatus) {
  if (status === MissionStatus.AVAILABLE) return '可接受';
  if (status === MissionStatus.ACCEPTED) return '进行中';
  if (status === MissionStatus.SUBMITTED) return '待评审';
  if (status === MissionStatus.COMPLETED) return '已完成';
  return '未解锁';
}

function recommendedAction(status: MissionStatus) {
  if (status === MissionStatus.AVAILABLE) return '阅读任务需求，确认交付物，然后接受任务。';
  if (status === MissionStatus.ACCEPTED) return '整理报告或成果，准备提交给 AI 导师评审。';
  if (status === MissionStatus.SUBMITTED) return '等待 AI 导师评审，完成后查看反馈。';
  if (status === MissionStatus.COMPLETED) return '查看反馈，把成果沉淀到成长档案。';
  return '完成前置任务后解锁。';
}

function actionButtonText(status: MissionStatus) {
  if (status === MissionStatus.AVAILABLE) return '接受任务并开始';
  if (status === MissionStatus.ACCEPTED) return '继续提交';
  if (status === MissionStatus.SUBMITTED) return '查看评审';
  if (status === MissionStatus.COMPLETED) return '查看报告';
  return '任务未解锁';
}
