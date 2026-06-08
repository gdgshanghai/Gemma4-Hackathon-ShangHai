import React from 'react';
import { useRouter } from 'next/navigation';
import { PixelCard, PixelButton } from '@/components/pixel';

interface FeynmanChallengeCardProps {
  careerId: string;
  missionId?: string;
}

const feynmanChallenges = {
  'software-engineer': [
    '请解释：为什么必须先复现 Bug？',
    '请用最简单的语言说明：什么是单元测试？'
  ],
  'data-analyst': [
    '请用最简单的语言解释：什么是用户活跃度？',
    '请说明：什么是数据清洗？'
  ]
};

export default function FeynmanChallengeCard({ careerId, missionId }: FeynmanChallengeCardProps) {
  const router = useRouter();
  
  const challenges = feynmanChallenges[careerId as keyof typeof feynmanChallenges] 
    || feynmanChallenges['software-engineer'];
  const challenge = challenges[0];

  const handleStartChallenge = () => {
    const defaultMissionId = missionId || 'mission-001';
    router.push(`/feynman/${defaultMissionId}`);
  };

  return (
    <PixelCard title="🧠 费曼挑战">
      <div className="space-y-4">
        {/* 挑战问题预览 */}
        <div className="p-3 bg-amber-900/20 border-2 border-amber-700">
          <p className="text-amber-300 font-medium text-sm">{challenge}</p>
        </div>

        <div className="text-center">
          <p className="text-slate-400 text-sm mb-3">
            用简单语言解释概念，证明你真的理解了！
          </p>
          <PixelButton 
            variant="primary" 
            onClick={handleStartChallenge}
            className="w-full"
          >
            🚀 开始挑战
          </PixelButton>
        </div>

        {/* 提示 */}
        <p className="text-xs text-slate-500 italic">
          💡 费曼学习法：用简单语言解释概念，如果做不到说明还没理解。
        </p>
      </div>
    </PixelCard>
  );
}
