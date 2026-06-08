import React from 'react';
import { PixelProgress, PixelBadge } from '@/components/pixel';
import { EmptyState } from '@/components/common';

interface Skill {
  id: string;
  name: string;
  level: number;
  maxLevel: number;
  exp: number;
  expToNext: number;
  unlocked: boolean;
}

interface PortfolioSkillSummaryProps {
  softwareEngineerSkills: Skill[];
  dataAnalystSkills: Skill[];
}

export default function PortfolioSkillSummary({
  softwareEngineerSkills,
  dataAnalystSkills
}: PortfolioSkillSummaryProps) {
  const hasSkills = softwareEngineerSkills.length > 0 || dataAnalystSkills.length > 0;

  if (!hasSkills) {
    return (
      <div>
        <h2 className="text-xl font-bold text-amber-500 mb-3 flex items-center gap-2">
          <span>🎯</span>
          <span>技能成长</span>
        </h2>
        <EmptyState
          description="完成任务后会在这里显示技能成长记录。"
        />
      </div>
    );
  }

  const renderSkillGroup = (skills: Skill[], title: string, icon: string) => {
    if (skills.length === 0) return null;
    
    return (
      <div className="mb-4 last:mb-0">
        <h3 className="text-base font-bold text-slate-200 mb-2 flex items-center gap-2 border-b-2 border-slate-700 pb-1">
          <span>{icon}</span>
          <span>{title}</span>
        </h3>
        <div className="space-y-2">
          {skills.map((skill) => (
            <div 
              key={skill.id}
              className={`p-2 border-3 ${skill.unlocked ? 'bg-green-900/30 border-green-600' : 'bg-slate-800 border-slate-700'}`}
            >
              <div className="flex justify-between items-center mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-slate-300 font-medium text-sm">{skill.name}</span>
                  {skill.unlocked && (
                    <PixelBadge variant="fun" className="text-xs py-0 px-2">
                      Lv.{skill.level}
                    </PixelBadge>
                  )}
                </div>
                {skill.unlocked ? (
                  <span className="text-green-500 text-xs">
                    {skill.exp}/{skill.expToNext} XP
                  </span>
                ) : (
                  <span className="text-slate-600 text-xs">未解锁</span>
                )}
              </div>
              {skill.unlocked && (
                <PixelProgress 
                  value={(skill.exp / skill.expToNext) * 100} 
                  color="#10b981"
                />
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div>
      <h2 className="text-xl font-bold text-amber-500 mb-3 flex items-center gap-2">
        <span>🎯</span>
        <span>技能成长</span>
      </h2>
      {renderSkillGroup(softwareEngineerSkills, '软件工程技能', '⚙️')}
      {renderSkillGroup(dataAnalystSkills, '数据分析技能', '📊')}
    </div>
  );
}
