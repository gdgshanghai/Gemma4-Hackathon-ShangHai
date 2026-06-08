'use client';

import React, { useState } from 'react';
import CareerIslandNode, { IslandStatus } from './CareerIslandNode';
import { IMAGES } from '@/constants/images';

export interface CareerMapIsland {
  id: string;
  name: string;
  islandName: string;
  icon: string;
  status: IslandStatus;
  description: string;
  position: { x: number; y: number };
  mentor: string;
  currentTheme: string;
  representativeTask: string;
  skills: string[];
  targetAudience: string;
}

interface CareerWorldMapProps {
  onIslandSelect: (island: CareerMapIsland | null) => void;
  careerOverrides?: {
    id: string;
    name: string;
    description: string;
    unlocked: boolean;
  }[];
}

const islands: CareerMapIsland[] = [
  {
    id: 'data-analyst',
    name: '初级数据分析师',
    islandName: '数据山脉',
    icon: 'DA',
    status: 'available',
    description: '从用户行为数据里找到业务线索。',
    position: { x: 24, y: 34 },
    mentor: '数据导师',
    currentTheme: '用户行为分析',
    representativeTask: '分析社区论坛用户活跃度下降原因',
    skills: ['指标口径', '分组聚合', '可视化报告'],
    targetAudience: '想学习数据分析和业务洞察的计算机系学生',
  },
  {
    id: 'software-engineer',
    name: '初级软件工程师',
    islandName: '硅之岛',
    icon: 'SE',
    status: 'available',
    description: '从复现问题到交付代码修复。',
    position: { x: 64, y: 55 },
    mentor: '工程导师',
    currentTheme: 'Bug 复现与修复',
    representativeTask: '复现并修复一个线上问题',
    skills: ['调试', '单元测试', 'API 设计'],
    targetAudience: '想学习真实工程流程的学生',
  },
  {
    id: 'product-designer',
    name: '产品经理实训生',
    islandName: '产品设计港',
    icon: 'PM',
    status: 'available',
    description: '把用户需求变成可执行产品方案。',
    position: { x: 42, y: 74 },
    mentor: '产品导师',
    currentTheme: '用户旅程与原型表达',
    representativeTask: '设计一个任务管理与反馈闭环',
    skills: ['需求拆解', '用户旅程', '原型说明'],
    targetAudience: '想把技术能力连接到产品判断的学生',
  },
  {
    id: 'ai-researcher',
    name: 'AI 研究实习生',
    islandName: 'AI 研究塔',
    icon: 'AI',
    status: 'locked',
    description: '把模型想法变成可验证实验。',
    position: { x: 76, y: 25 },
    mentor: '研究导师',
    currentTheme: '模型评测与实验设计',
    representativeTask: '设计一个小型模型评估实验',
    skills: ['提示工程', '模型评估', '实验复盘'],
    targetAudience: '想探索 AI 研究和应用验证的学生',
  },
];

const connections = [
  { from: 'data-analyst', to: 'software-engineer' },
  { from: 'data-analyst', to: 'product-designer' },
  { from: 'software-engineer', to: 'ai-researcher' },
  { from: 'product-designer', to: 'ai-researcher' },
];

export default function CareerWorldMap({ onIslandSelect, careerOverrides = [] }: CareerWorldMapProps) {
  const [selectedIslandId, setSelectedIslandId] = useState<string | null>(null);
  const mergedIslands = islands.map((island) => {
    const override = careerOverrides.find((item) => item.id === island.id);
    return override
      ? {
          ...island,
          name: override.name || island.name,
          description: override.description || island.description,
          status: (override.unlocked ? island.status === 'locked' ? 'available' : island.status : 'locked') as IslandStatus,
        }
      : island;
  });

  const handleIslandSelect = (island: CareerMapIsland) => {
    const nextId = selectedIslandId === island.id ? null : island.id;
    setSelectedIslandId(nextId);
    onIslandSelect(nextId ? island : null);
  };

  const getIslandById = (id: string) => mergedIslands.find((island) => island.id === id);

  return (
    <div
      className="relative h-[640px] w-full overflow-hidden border-4 border-slate-700 bg-slate-950"
      style={{
        backgroundImage: `linear-gradient(180deg, rgba(2,6,23,0.54), rgba(2,6,23,0.84)), url(${IMAGES.CAREER_CAMPUS_BACKDROP})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_25%,rgba(20,184,166,0.18),transparent_32%),radial-gradient(circle_at_70%_70%,rgba(245,158,11,0.16),transparent_36%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.026)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.026)_1px,transparent_1px)] bg-[length:28px_28px]" />

      <svg className="absolute inset-0 h-full w-full">
        {connections.map((connection) => {
          const from = getIslandById(connection.from);
          const to = getIslandById(connection.to);
          if (!from || !to) return null;
          return (
            <line
              key={`${connection.from}-${connection.to}`}
              x1={`${from.position.x}%`}
              y1={`${from.position.y}%`}
              x2={`${to.position.x}%`}
              y2={`${to.position.y}%`}
              stroke="#475569"
              strokeWidth="3"
              strokeDasharray="8 8"
              strokeLinecap="round"
            />
          );
        })}
      </svg>

      {mergedIslands.map((island) => (
        <CareerIslandNode
          key={island.id}
          {...island}
          isSelected={selectedIslandId === island.id}
          onSelect={() => handleIslandSelect(island)}
        />
      ))}
    </div>
  );
}
