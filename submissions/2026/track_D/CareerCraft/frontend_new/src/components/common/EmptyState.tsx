'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import PixelButton from '@/components/pixel/PixelButton';
import PixelCard from '@/components/pixel/PixelCard';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: string;
  action?: {
    label: string;
    onClick?: () => void;
    href?: string;
  };
}

export default function EmptyState({
  title = '暂无内容',
  description = '完成任务后，这里会显示你的成长记录。',
  icon = 'LOG',
  action,
}: EmptyStateProps) {
  const router = useRouter();

  const handleAction = () => {
    if (action?.href) {
      router.push(action.href);
      return;
    }

    action?.onClick?.();
  };

  return (
    <PixelCard className="py-12 text-center">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center border-2 border-amber-600 bg-slate-950 font-mono text-sm font-bold text-amber-300">
        {icon}
      </div>
      <h3 className="pixel-title mb-3 text-xl font-bold text-amber-300">{title}</h3>
      <p className="mx-auto mb-6 max-w-md leading-7 text-slate-400">{description}</p>
      {action ? (
        <PixelButton variant="primary" onClick={handleAction}>
          {action.label}
        </PixelButton>
      ) : null}
    </PixelCard>
  );
}
