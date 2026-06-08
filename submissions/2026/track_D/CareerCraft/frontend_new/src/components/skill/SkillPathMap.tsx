import React from 'react';
import SkillNodeCard, { getSkillStatus } from './SkillNodeCard';
import { SkillNode } from '@/types';

interface SkillPathMapProps {
  skills: SkillNode[];
  onSkillClick: (skill: SkillNode) => void;
}

export default function SkillPathMap({ skills, onSkillClick }: SkillPathMapProps) {
  // 按 x,y 坐标排序技能，构建路径
  const sortedSkills = [...skills].sort((a, b) => {
    if (a.y !== b.y) return a.y - b.y;
    return a.x - b.x;
  });

  // 按层级分组
  const skillsByLevel: { [level: number]: SkillNode[] } = {};
  sortedSkills.forEach(skill => {
    if (!skillsByLevel[skill.y]) {
      skillsByLevel[skill.y] = [];
    }
    skillsByLevel[skill.y].push(skill);
  });

  // 层级数组
  const levels = Object.keys(skillsByLevel)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div className="relative">
      {/* 桌面端 - 网格布局 */}
      <div className="hidden lg:block">
        <div className="relative py-8">
          {/* 连接线 */}
          <ConnectionLines skills={skills} />

          {/* 技能节点网格 */}
          <div className="space-y-8">
            {levels.map((level) => (
              <div key={level} className="flex justify-center gap-6">
                {skillsByLevel[level].map((skill) => (
                  <div key={skill.id} className="w-40">
                    <SkillNodeCard 
                      skill={skill} 
                      onClick={() => onSkillClick(skill)} 
                    />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 移动端 - 垂直列表 */}
      <div className="lg:hidden">
        <div className="space-y-4">
          {sortedSkills.map((skill) => (
            <SkillNodeCard 
              key={skill.id} 
              skill={skill} 
              onClick={() => onSkillClick(skill)} 
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// 连接线组件
function ConnectionLines({ skills }: { skills: SkillNode[] }) {
  // 查找父子关系
  const connections: { from: SkillNode; to: SkillNode }[] = [];

  skills.forEach(child => {
    child.prerequisites.forEach(parentId => {
      const parent = skills.find(s => s.id === parentId);
      if (parent) {
        connections.push({ from: parent, to: child });
      }
    });
  });

  if (connections.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none">
      {connections.map((conn, idx) => (
        <div 
          key={idx}
          className="absolute"
          style={{
            // 简单的线连接，我们可以用视觉效果
            // 在实际应用中可以用 SVG，但这里用简单的装饰性线条
          }}
        />
      ))}
      
      {/* 装饰性背景连线效果 */}
      <div className="absolute top-24 left-1/2 transform -translate-x-1/2 w-1 h-12 bg-slate-700" />
      <div className="absolute top-44 left-1/2 transform -translate-x-1/2 flex gap-20">
        <div className="w-1 h-12 bg-slate-700" />
        <div className="w-1 h-12 bg-slate-700" />
      </div>
    </div>
  );
}
