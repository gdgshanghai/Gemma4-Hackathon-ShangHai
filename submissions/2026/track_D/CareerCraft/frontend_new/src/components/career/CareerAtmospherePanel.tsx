import React from 'react';
import { PixelBadge } from '@/components/pixel';

interface CareerAtmospherePanelProps {
  careerId: string;
}

const ATMOSPHERE_CONFIG: Record<string, {
  islandStatus: string;
  trainingTheme: string;
  mentorTip: string;
  practiceMethod: string;
}> = {
  'software-engineer': {
    islandStatus: '工程工坊运行中',
    trainingTheme: '复现、定位、修复',
    mentorTip: '先写出最小复现场景，再考虑解决方案。',
    practiceMethod: '用本地环境刻意练习调试和测试。',
  },
  'data-analyst': {
    islandStatus: '数据雾气较重',
    trainingTheme: '从异常值中识别业务问题',
    mentorTip: '不要急着画图，先理解字段含义。',
    practiceMethod: '用真实数据集做探索性分析。',
  },
  'product-designer': {
    islandStatus: '港口工作室开放',
    trainingTheme: '需求、用户旅程、方案表达',
    mentorTip: '不要一上来画界面，先说明用户是谁、问题是什么。',
    practiceMethod: '把一个模糊需求拆成可验证的产品假设。',
  },
};

export default function CareerAtmospherePanel({ careerId }: CareerAtmospherePanelProps) {
  const config = ATMOSPHERE_CONFIG[careerId] || {
    islandStatus: '路线建设中',
    trainingTheme: '职业探索预告',
    mentorTip: '先完成前置路线，再进入更高阶试炼。',
    practiceMethod: '记录你对这个职业的三个问题。',
  };

  return (
    <div className="border-4 border-slate-700 bg-slate-950/72 p-5">
      <h3 className="mb-4 text-lg font-bold text-amber-300">今日岛屿状态</h3>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <InfoTile title="今日岛屿" value={config.islandStatus} />
        <InfoTile title="训练主题" value={config.trainingTheme} />

        <div className="border-2 border-slate-700 bg-slate-900/70 p-3 md:col-span-2">
          <div className="mb-2 text-xs text-slate-400">导师提示</div>
          <p className="text-sm italic text-slate-300">“{config.mentorTip}”</p>
        </div>

        <div className="border-2 border-slate-700 bg-slate-900/70 p-3 md:col-span-2">
          <div className="flex items-center gap-2">
            <PixelBadge variant="neutral" className="text-xs">推荐练习</PixelBadge>
            <span className="text-sm text-slate-300">{config.practiceMethod}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoTile({ title, value }: { title: string; value: string }) {
  return (
    <div className="border-2 border-slate-700 bg-slate-900/70 p-3">
      <div className="mb-1 text-xs text-slate-400">{title}</div>
      <div className="font-medium text-amber-300">{value}</div>
    </div>
  );
}
