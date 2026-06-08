'use client';

import React from 'react';
import { PixelBadge } from '@/components/pixel';
import { getCareerImage } from '@/constants/images';

export type IslandStatus = 'available' | 'locked' | 'in-progress' | 'completed';

interface CareerIslandNodeProps {
  id: string;
  name: string;
  islandName: string;
  icon: string;
  status: IslandStatus;
  description: string;
  position: { x: number; y: number };
  isSelected: boolean;
  onSelect: () => void;
}

export default function CareerIslandNode({
  id,
  name,
  islandName,
  icon,
  status,
  description,
  position,
  isSelected,
  onSelect,
}: CareerIslandNodeProps) {
  const isLocked = status === 'locked';
  const image = getCareerImage(id);
  const palette =
    status === 'available'
      ? 'border-emerald-500 bg-emerald-950/60 text-emerald-200'
      : status === 'in-progress'
        ? 'border-amber-500 bg-amber-950/60 text-amber-200'
        : status === 'completed'
          ? 'border-sky-500 bg-sky-950/60 text-sky-200'
          : 'border-slate-600 bg-slate-900/70 text-slate-400';

  return (
    <button
      type="button"
      className="absolute text-left transition-transform hover:-translate-y-1"
      style={{
        left: `${position.x}%`,
        top: `${position.y}%`,
        transform: `translate(-50%, -50%) ${isSelected ? 'scale(1.06)' : ''}`,
        zIndex: isSelected ? 10 : undefined,
      }}
      onClick={onSelect}
    >
      <div
        className={`relative w-[172px] overflow-hidden border-4 ${palette}`}
        style={{
          boxShadow: isSelected
            ? '0 0 20px rgba(245,158,11,0.32), inset -3px -3px 0 #020617, inset 3px 3px 0 rgba(255,255,255,0.12)'
            : 'inset -3px -3px 0 #020617, inset 3px 3px 0 rgba(255,255,255,0.10)',
        }}
      >
        {isLocked ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/78">
            <span className="border-2 border-slate-500 px-2 py-1 text-xs font-bold text-slate-300">
              即将开放
            </span>
          </div>
        ) : null}

        <div
          className="h-20 border-b-2 border-current"
          style={{
            backgroundImage: `linear-gradient(180deg, rgba(2,6,23,0.05), rgba(2,6,23,0.46)), url(${image})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        />

        <div className="p-3">
          <div className="mb-2 flex h-9 w-9 items-center justify-center border-2 border-current bg-slate-950/70 font-bold">
            {icon}
          </div>
          <p className="font-bold">{islandName}</p>
          <p className="mt-1 text-xs opacity-80">{name}</p>
          <div className="mt-3">
            <PixelBadge
              variant={
                status === 'available'
                  ? 'success'
                  : status === 'in-progress'
                    ? 'warning'
                    : status === 'completed'
                      ? 'fun'
                      : 'neutral'
              }
              className="text-xs"
            >
              {statusLabel(status)}
            </PixelBadge>
          </div>
          {!isLocked ? <p className="mt-3 text-xs leading-5 opacity-80">{description}</p> : null}
        </div>
      </div>
    </button>
  );
}

function statusLabel(status: IslandStatus) {
  if (status === 'available') return '可进入';
  if (status === 'in-progress') return '训练中';
  if (status === 'completed') return '已完成';
  return '预告';
}
