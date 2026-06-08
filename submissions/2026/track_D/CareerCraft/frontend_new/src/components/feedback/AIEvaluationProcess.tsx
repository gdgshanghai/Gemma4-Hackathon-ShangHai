import React, { useEffect, useState } from 'react';
import { PixelCard } from '@/components/pixel';
import EvaluationStepCard from './EvaluationStepCard';
import EvaluationDimensionCard from './EvaluationDimensionCard';
import EvaluationVerdictPanel from './EvaluationVerdictPanel';

interface AIEvaluationProcessProps {
  isSoftwareEngineer: boolean;
}

const evaluationSteps = [
  {
    step: 1,
    icon: '1',
    title: '读取任务要求',
    description: '确认职业场景、交付物和评分标准。',
  },
  {
    step: 2,
    icon: '2',
    title: '检查交付完整度',
    description: '核对报告、代码或补充材料是否覆盖关键要求。',
  },
  {
    step: 3,
    icon: '3',
    title: '分析问题拆解质量',
    description: '判断思路是否清楚，证据链是否能支撑结论。',
  },
  {
    step: 4,
    icon: '4',
    title: '生成成长建议',
    description: '把这次表现转化成下一次可练习的技能点。',
  },
];

export default function AIEvaluationProcess({ isSoftwareEngineer }: AIEvaluationProcessProps) {
  const [isEvaluating, setIsEvaluating] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsEvaluating(false), 700);
    return () => clearTimeout(timer);
  }, []);

  const dimensions = isSoftwareEngineer
    ? [
        {
          title: '问题复现',
          score: 22,
          maxScore: 25,
          observation: '复现路径比较清楚，能帮助队友快速定位问题。',
        },
        {
          title: '代码正确性',
          score: 20,
          maxScore: 25,
          observation: '整体逻辑成立，边界场景还可以继续补充。',
        },
        {
          title: '交付完整度',
          score: 21,
          maxScore: 25,
          observation: '修复说明和关键材料都有提交。',
        },
        {
          title: '测试覆盖',
          score: 19,
          maxScore: 25,
          observation: '已有基础测试，建议增加异常输入和回归用例。',
        },
      ]
    : [
        {
          title: '问题拆解',
          score: 22,
          maxScore: 25,
          observation: '能把活跃下降拆成时间、用户分层和行为路径几个方向。',
        },
        {
          title: '数据口径',
          score: 20,
          maxScore: 25,
          observation: '分析逻辑成立，指标定义还可以写得更明确。',
        },
        {
          title: '交付完整度',
          score: 21,
          maxScore: 25,
          observation: '报告包含背景、过程、结论，结构完整。',
        },
        {
          title: '建议可行性',
          score: 19,
          maxScore: 25,
          observation: '建议方向合理，下一步可补充优先级和验证方式。',
        },
      ];

  const totalScore = dimensions.reduce((sum, dimension) => sum + dimension.score, 0);
  const maxScore = dimensions.reduce((sum, dimension) => sum + dimension.maxScore, 0);
  const grade = totalScore >= 90 ? 'S' : totalScore >= 80 ? 'A' : totalScore >= 70 ? 'B+' : 'B';
  const summary = isSoftwareEngineer
    ? '你已经具备完成初级工程任务的能力。下一步建议加强边界测试、代码说明和问题复盘。'
    : '你已经具备完成初级数据分析任务的能力。下一步建议把指标口径和建议落地方式写得更具体。';

  return (
    <div className="space-y-6">
      <PixelCard title="AI 同事评审流程">
        <p className="mb-4 text-sm leading-6 text-slate-300">
          评审不是判题，而是模拟一次导师和同事对交付物的复盘。
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          {evaluationSteps.map((step) => (
            <EvaluationStepCard key={step.step} {...step} isCompleted={!isEvaluating} />
          ))}
        </div>
      </PixelCard>

      <EvaluationVerdictPanel
        isSoftwareEngineer={isSoftwareEngineer}
        isPassed={totalScore >= 60}
        grade={grade}
        totalScore={totalScore}
        maxScore={maxScore}
        summary={summary}
      />

      <PixelCard title="维度评分">
        <div className="grid gap-4 md:grid-cols-2">
          {dimensions.map((dimension) => (
            <EvaluationDimensionCard key={dimension.title} {...dimension} />
          ))}
        </div>
      </PixelCard>
    </div>
  );
}
