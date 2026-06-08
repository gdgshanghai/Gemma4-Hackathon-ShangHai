'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { PixelBadge, PixelButton, PixelCard } from '@/components/pixel';
import { getCareerImage } from '@/constants/images';
import { IslandStatus } from './CareerIslandNode';

interface CareerPreviewPanelProps {
  career: {
    id: string;
    name: string;
    islandName: string;
    icon: string;
    status: IslandStatus;
    description: string;
    mentor: string;
    currentTheme: string;
    representativeTask: string;
    skills: string[];
    targetAudience: string;
  } | null;
}

export default function CareerPreviewPanel({ career }: CareerPreviewPanelProps) {
  const router = useRouter();

  if (!career) {
    return (
      <PixelCard title="职业预览" className="h-full bg-slate-950/84">
        <div className="py-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center border-4 border-amber-600 text-lg font-bold text-amber-300">
            MAP
          </div>
          <p className="text-sm leading-6 text-slate-400">
            点击地图上的职业岛，查看导师、任务主题和适合人群。
          </p>
        </div>
      </PixelCard>
    );
  }

  const isAvailable =
    career.status === 'available' || career.status === 'in-progress' || career.status === 'completed';
  const image = getCareerImage(career.id);

  return (
    <PixelCard title="职业预览" className="h-full bg-slate-950/84">
      <div className="space-y-4">
        <div
          className="h-36 border-2 border-slate-700"
          style={{
            backgroundImage: `linear-gradient(90deg, rgba(2,6,23,0.68), rgba(2,6,23,0.12)), url(${image})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        />

        <div className="border-2 border-slate-700 bg-slate-900/70 p-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center border-2 border-amber-500 font-bold text-amber-300">
              {career.icon}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="pixel-title text-lg text-amber-300">{career.islandName}</h3>
              <p className="mt-1 text-sm text-slate-300">{career.name}</p>
              <div className="mt-2">
                <PixelBadge variant={isAvailable ? 'success' : 'neutral'}>
                  {isAvailable ? '可进入' : '即将开放'}
                </PixelBadge>
              </div>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-300">{career.description}</p>
        </div>

        <InfoBlock title="导师" text={career.mentor} />
        <InfoBlock title="当前训练主题" text={career.currentTheme} />
        <InfoBlock title="代表任务" text={career.representativeTask} />

        <div>
          <h4 className="mb-2 text-sm font-bold text-slate-300">可训练技能</h4>
          <div className="flex flex-wrap gap-2">
            {career.skills.map((skill) => (
              <PixelBadge key={skill} variant="neutral" className="text-xs">
                {skill}
              </PixelBadge>
            ))}
          </div>
        </div>

        <InfoBlock title="适合人群" text={career.targetAudience} />

        {isAvailable ? (
          <PixelButton fullWidth onClick={() => router.push(`/career/${career.id}`)}>
            进入职业岛
          </PixelButton>
        ) : (
          <div className="border-2 border-slate-700 bg-slate-900/60 p-4 text-center text-sm text-slate-400">
            这条路线正在建设中，先完成前置岛屿训练。
          </div>
        )}
      </div>
    </PixelCard>
  );
}

function InfoBlock({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <h4 className="mb-1 text-sm font-bold text-slate-300">{title}</h4>
      <p className="text-sm leading-6 text-slate-400">{text}</p>
    </div>
  );
}
