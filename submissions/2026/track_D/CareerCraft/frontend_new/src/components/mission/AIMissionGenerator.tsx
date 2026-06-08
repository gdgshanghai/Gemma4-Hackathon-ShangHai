import React, { useEffect, useState } from 'react';
import { PixelBadge, PixelButton, PixelDialog, PixelProgress } from '@/components/pixel';
import { missionService } from '@/services';
import { Mission } from '@/types';
import type { GeneratedMission } from './GeneratedMissionCard';

const TASK_DIRECTIONS = {
  'data-analyst': [
    { value: 'data-cleaning', label: '数据清洗' },
    { value: 'sql-analysis', label: 'SQL 分析' },
    { value: 'visualization', label: '可视化报告' },
  ],
  'software-engineer': [
    { value: 'bug-fix', label: 'Bug 修复' },
    { value: 'unit-test', label: '单元测试' },
    { value: 'api-design', label: 'API 设计' },
  ],
  default: [
    { value: 'data-cleaning', label: '数据清洗' },
    { value: 'sql-analysis', label: 'SQL 分析' },
    { value: 'visualization', label: '可视化报告' },
  ],
};

const DIFFICULTIES = [
  { value: 'easy', label: '入门' },
  { value: 'medium', label: '进阶' },
  { value: 'hard', label: '挑战' },
];

const STYLES = [
  { value: 'ticket', label: '企业工单' },
  { value: 'project', label: '项目委托' },
  { value: 'interview', label: '面试实战' },
  { value: 'feynman', label: '费曼讲解型' },
];

const GENERATION_STEPS = [
  { step: 1, label: '读取职业方向' },
  { step: 2, label: '分析技能缺口' },
  { step: 3, label: '检索资料馆任务脚本' },
  { step: 4, label: '生成企业场景委托' },
  { step: 5, label: '输出评审标准' },
];

interface AIMissionGeneratorProps {
  open: boolean;
  onClose: () => void;
  careerId: string;
  onMissionAccepted?: (mission: Mission, source: 'api' | 'fallback') => void;
}

function mapMissionToGenerated(mission: Mission, type: string): GeneratedMission {
  return {
    id: mission.id,
    title: mission.title,
    aiLead: mission.aiLead || 'AI Mission Orchestrator',
    businessBackground: mission.background || mission.description,
    objectives: mission.objectives,
    deliverables: mission.deliverables,
    reviewCriteria: mission.criteria,
    recommendedSkills: mission.rewardSkills.length > 0 ? mission.rewardSkills : ['Portfolio evidence', 'Task delivery'],
    recommendedResources: mission.recommendedResources?.length
      ? mission.recommendedResources
      : mission.deliverables.slice(0, 2),
    estimatedTime: mission.estimatedTime || (mission.difficulty === 'hard' ? '60-90 min' : mission.difficulty === 'medium' ? '40-60 min' : '20-30 min'),
    rewardXP: mission.rewardExp,
    difficulty: mission.difficulty,
    type: mission.missionStyle || type,
    mockDataUrl: mission.mockDataUrl,
  };
}

export default function AIMissionGenerator({ open, onClose, careerId, onMissionAccepted }: AIMissionGeneratorProps) {
  const [direction, setDirection] = useState('data-cleaning');
  const [difficulty, setDifficulty] = useState('easy');
  const [style, setStyle] = useState('ticket');
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [generationMessage, setGenerationMessage] = useState('');
  const [generatedMission, setGeneratedMission] = useState<GeneratedMission | null>(null);
  const [acceptedMission, setAcceptedMission] = useState<Mission | null>(null);
  const [missionSource, setMissionSource] = useState<'api' | 'fallback' | null>(null);

  const directions = TASK_DIRECTIONS[careerId as keyof typeof TASK_DIRECTIONS] || TASK_DIRECTIONS.default;

  useEffect(() => {
    if (!directions.some((option) => option.value === direction)) {
      setDirection(directions[0]?.value || 'data-cleaning');
    }
  }, [careerId, direction, directions]);

  const handleGenerateFromApi = async () => {
    setIsGenerating(true);
    setCurrentStep(0);
    setProgress(0);
    setGenerationMessage('正在连接后端任务生成接口，真实生成可能需要 1-3 分钟...');
    setGeneratedMission(null);
    setAcceptedMission(null);
    setMissionSource(null);

    let stepIndex = 0;
    const interval = window.setInterval(() => {
      const nextStep = Math.min(stepIndex, GENERATION_STEPS.length - 1);
      setCurrentStep(nextStep);
      setProgress(((nextStep + 1) / GENERATION_STEPS.length) * 100);
      stepIndex += 1;
    }, 500);

    try {
      const result = await missionService.generateMissionWithSource(careerId, difficulty, direction, style);
      setAcceptedMission(result.mission);
      setMissionSource(result.source);
      setGeneratedMission(mapMissionToGenerated(result.mission, style));
      setGenerationMessage(result.source === 'api' ? '已从后端 API 生成任务。' : '后端暂不可用或等待超时，已生成离线模拟任务。');
    } catch (error) {
      console.warn('Mission generation failed without service fallback.', error);
      setGeneratedMission(null);
      setAcceptedMission(null);
      setMissionSource(null);
      setGenerationMessage('任务生成失败，结果未保存到后端。请确认后端可用后重试。');
    } finally {
      window.clearInterval(interval);
      setCurrentStep(GENERATION_STEPS.length);
      setProgress(100);
      setIsGenerating(false);
    }
  };

  const handleAccept = () => {
    if (acceptedMission && missionSource) {
      onMissionAccepted?.(acceptedMission, missionSource);
    }
    onClose();
  };

  return (
    <PixelDialog
      open={open}
      onClose={onClose}
      title={isGenerating ? 'AI 导师正在生成任务' : 'AI 任务生成器'}
    >
      {!generatedMission ? (
        <div className="space-y-4">
          <div className="border-2 border-slate-700 bg-slate-950 p-4">
            <div className="font-mono text-xs uppercase text-emerald-300">Mission Generation</div>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              AI 导师将根据你的职业方向和技能水平，为你生成一份个性化的任务委托。
            </p>
          </div>

          {!isGenerating && generationMessage ? (
            <div className="border-2 border-red-700 bg-red-950/35 p-3 text-sm font-bold text-red-100">
              {generationMessage}
            </div>
          ) : null}

          {isGenerating ? (
            <div className="border-2 border-amber-700/70 bg-amber-950/18 p-4">
              <div className="space-y-3">
                {GENERATION_STEPS.map((step, index) => {
                  const isCompleted = index < currentStep;
                  const isActive = index === currentStep && isGenerating;

                  return (
                    <div
                      key={step.step}
                      className={`flex items-center gap-3 ${
                        isCompleted
                          ? 'text-emerald-300'
                          : isActive
                            ? 'text-amber-300'
                            : 'text-slate-500'
                      }`}
                    >
                      <div className={`flex h-6 w-6 shrink-0 items-center justify-center border font-mono text-xs font-bold ${
                        isCompleted
                          ? 'border-emerald-500 bg-emerald-950/30 text-emerald-300'
                          : isActive
                            ? 'border-amber-500 bg-amber-950/30 text-amber-300'
                            : 'border-slate-700 bg-slate-900 text-slate-500'
                      }`}>
                        {isCompleted ? '✓' : String(step.step)}
                      </div>
                      <span className={`text-sm ${isActive ? 'font-bold' : ''}`}>{step.label}</span>
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 space-y-2">
                <PixelProgress value={progress} color="#f59e0b" />
                <div className="text-sm italic text-amber-300">{generationMessage}</div>
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="border-2 border-slate-700 bg-slate-900/70 p-4">
                  <div className="mb-3 font-bold text-slate-300">任务方向</div>
                  <div className="space-y-2">
                    {directions.map((option) => {
                      const selected = option.value === direction;
                      return (
                        <button
                          key={option.value}
                          onClick={() => setDirection(option.value)}
                          className={`w-full border p-2 text-left text-sm transition-colors ${
                            selected
                              ? 'border-amber-500 bg-amber-500/20 text-amber-200'
                              : 'border-slate-700 bg-slate-950/50 text-slate-400 hover:border-amber-600'
                          }`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="border-2 border-slate-700 bg-slate-900/70 p-4">
                  <div className="mb-3 font-bold text-slate-300">难度</div>
                  <div className="space-y-2">
                    {DIFFICULTIES.map((option) => {
                      const selected = option.value === difficulty;
                      const difficultyColors = {
                        easy: selected ? 'border-green-500 bg-green-500/20 text-green-200' : 'border-slate-700 bg-slate-950/50 text-slate-400 hover:border-green-600',
                        medium: selected ? 'border-amber-500 bg-amber-500/20 text-amber-200' : 'border-slate-700 bg-slate-950/50 text-slate-400 hover:border-amber-600',
                        hard: selected ? 'border-red-500 bg-red-500/20 text-red-200' : 'border-slate-700 bg-slate-950/50 text-slate-400 hover:border-red-600',
                      };
                      return (
                        <button
                          key={option.value}
                          onClick={() => setDifficulty(option.value)}
                          className={`w-full border p-2 text-left text-sm transition-colors ${difficultyColors[option.value as 'easy' | 'medium' | 'hard']}`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="border-2 border-slate-700 bg-slate-900/70 p-4">
                  <div className="mb-3 font-bold text-slate-300">任务风格</div>
                  <div className="space-y-2">
                    {STYLES.map((option) => {
                      const selected = option.value === style;
                      return (
                        <button
                          key={option.value}
                          onClick={() => setStyle(option.value)}
                          className={`w-full border p-2 text-left text-sm transition-colors ${
                            selected
                              ? 'border-amber-500 bg-amber-500/20 text-amber-200'
                              : 'border-slate-700 bg-slate-950/50 text-slate-400 hover:border-amber-600'
                          }`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-700">
                <PixelButton variant="secondary" onClick={onClose}>取消</PixelButton>
                <PixelButton onClick={handleGenerateFromApi} disabled={isGenerating}>生成任务</PixelButton>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="border-2 border-slate-700 bg-slate-950 p-4">
            <div className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-300">AI Generated</div>
            <h3 className="mt-2 text-xl font-bold text-amber-300">{generatedMission.title}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              <PixelBadge variant={generatedMission.difficulty === 'easy' ? 'fun' : generatedMission.difficulty === 'medium' ? 'honor' : 'warning'}>
                {generatedMission.difficulty === 'easy' ? '入门' : generatedMission.difficulty === 'medium' ? '进阶' : '挑战'}
              </PixelBadge>
              <PixelBadge variant="honor">+{generatedMission.rewardXP} XP</PixelBadge>
              <PixelBadge variant="neutral">{generatedMission.estimatedTime}</PixelBadge>
              {missionSource ? (
                <PixelBadge variant={missionSource === 'api' ? 'success' : 'warning'}>
                  {missionSource === 'api' ? 'API' : 'Fallback'}
                </PixelBadge>
              ) : null}
            </div>
            {generatedMission.mockDataUrl ? (
              <PixelButton
                variant="secondary"
                className="mt-3"
                onClick={() => window.open(generatedMission.mockDataUrl, '_blank', 'noopener,noreferrer')}
              >
                下载任务数据集
              </PixelButton>
            ) : null}
          </div>

          <div className="border-2 border-slate-700 bg-slate-950 p-4">
            <h4 className="font-bold text-amber-300">任务背景</h4>
            <p className="mt-2 text-sm leading-6 text-slate-300">{generatedMission.businessBackground}</p>
          </div>

          <div className="border-2 border-slate-700 bg-slate-950 p-4">
            <h4 className="font-bold text-amber-300">任务目标</h4>
            <ul className="mt-2 space-y-2">
              {generatedMission.objectives.map((obj, idx) => (
                <li key={idx} className="flex items-start gap-3 text-sm leading-6 text-slate-300">
                  <span className="font-mono font-bold text-amber-400">OBJ</span>
                  <span>{obj}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="border-2 border-slate-700 bg-slate-950 p-4">
            <h4 className="font-bold text-amber-300">交付物</h4>
            <ul className="mt-2 space-y-2">
              {generatedMission.deliverables.map((deliverable, idx) => (
                <li key={idx} className="flex items-start gap-3 text-sm leading-6 text-slate-300">
                  <span className="font-mono font-bold text-emerald-400">OUT</span>
                  <span>{deliverable}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="border-2 border-slate-700 bg-slate-950 p-4">
            <h4 className="font-bold text-amber-300">评审标准</h4>
            <div className="mt-3 flex flex-wrap gap-2">
              {generatedMission.reviewCriteria.map((criteria, idx) => (
                <PixelBadge key={idx} variant="neutral">{criteria}</PixelBadge>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="border-2 border-slate-700 bg-slate-950 p-4">
              <h4 className="font-bold text-amber-300">推荐技能</h4>
              <div className="mt-3 flex flex-wrap gap-2">
                {generatedMission.recommendedSkills.map((skill, idx) => (
                  <PixelBadge key={idx} variant="fun">{skill}</PixelBadge>
                ))}
              </div>
            </div>

            <div className="border-2 border-slate-700 bg-slate-950 p-4">
              <h4 className="font-bold text-amber-300">推荐资源</h4>
              <ul className="mt-3 space-y-2">
                {generatedMission.recommendedResources.map((resource, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm leading-6 text-slate-300">
                    <span className="font-mono text-amber-400">›</span>
                    <span>{resource}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <PixelButton variant="secondary" onClick={onClose}>关闭</PixelButton>
            <PixelButton variant="secondary" onClick={handleGenerateFromApi}>重新生成</PixelButton>
            <PixelButton onClick={handleAccept}>接受委托</PixelButton>
          </div>
        </div>
      )}
    </PixelDialog>
  );
}
