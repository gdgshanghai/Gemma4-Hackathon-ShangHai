'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { PixelButton, PixelBadge } from '@/components/pixel';
import { ROUTES } from '@/constants';

interface PageHeaderProps {
  title: string;
  description?: string;
  showBackButton?: boolean;
  backRoute?: string;
  rightContent?: React.ReactNode;
}

export default function PageHeader({ 
  title, 
  description,
  showBackButton = false,
  backRoute,
  rightContent
}: PageHeaderProps) {
  const router = useRouter();

  const handleBack = () => {
    if (backRoute) {
      router.push(backRoute);
    } else {
      router.push(ROUTES.LOBBY);
    }
  };

  return (
    <header className="pixel-page-header border-b-4 border-slate-700 bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 py-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            {showBackButton && (
              <PixelButton variant="ghost" onClick={handleBack}>
                ← 返回
              </PixelButton>
            )}
            <div>
              <h1 className="pixel-title text-2xl font-bold text-amber-400">{title}</h1>
              {description && (
                <p className="mt-1 max-w-3xl text-slate-400 text-sm leading-6">{description}</p>
              )}
            </div>
          </div>
          {rightContent || (
            <div className="flex items-center gap-2 text-slate-400">
              <PixelBadge variant="neutral">
                <span className="text-amber-500 font-bold">Lv.1</span>
                {' '}职业冒险者
              </PixelBadge>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
