'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useUserStore } from '@/stores/userStore';
import { ROUTES } from '@/constants';

interface AppShellProps {
  children: React.ReactNode;
  className?: string;
}

export default function AppShell({ children, className = '' }: AppShellProps) {
  const { currentCareerId, totalXp } = useUserStore();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { label: '首页', href: ROUTES.HOME, icon: 'HOME' },
    { label: '职业大陆', href: ROUTES.LOBBY, icon: 'MAP' },
    ...(currentCareerId ? [{ label: '我的职业岛', href: ROUTES.CAREER(currentCareerId), icon: 'ISLE' }] : []),
    {
      label: '工程师社区',
      href: currentCareerId ? `${ROUTES.COMMUNITY}?career=${currentCareerId}` : ROUTES.COMMUNITY,
      icon: 'HELP',
    },
    { label: '作品集', href: ROUTES.PORTFOLIO, icon: 'FILE' },
  ];

  return (
    <div className={`min-h-screen bg-slate-900 ${className}`}>
      <div className="crt-screen">
        <nav className="sticky top-0 z-50 border-b-4 border-slate-700 bg-slate-800/95 backdrop-blur">
          <div className="mx-auto max-w-7xl px-4">
            <div className="flex h-14 items-center justify-between">
              <Link href={ROUTES.HOME} className="flex items-center gap-2 font-bold text-amber-400 hover:text-amber-300">
                <span className="border-2 border-amber-500 px-1 font-mono text-[10px]">CC</span>
                <span className="pixel-title hidden text-sm sm:inline">CareerCraft</span>
              </Link>

              <div className="hidden items-center gap-1 md:flex">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="flex items-center gap-2 border-2 border-transparent px-3 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:bg-slate-700/50 hover:text-amber-400"
                  >
                    <span className="font-mono text-[9px] text-slate-500">{item.icon}</span>
                    <span>{item.label}</span>
                  </Link>
                ))}
              </div>

              <div className="flex items-center gap-3">
                {totalXp > 0 ? <div className="hidden text-xs font-bold text-amber-400 sm:block">{totalXp} XP</div> : null}
                <button
                  type="button"
                  className="border-2 border-slate-600 px-2 py-1 font-mono text-xs text-slate-300 md:hidden"
                  onClick={() => setMobileMenuOpen((value) => !value)}
                  aria-label="切换导航菜单"
                >
                  {mobileMenuOpen ? 'CLOSE' : 'MENU'}
                </button>
              </div>
            </div>
          </div>

          {mobileMenuOpen ? (
            <div className="border-t-2 border-slate-700 bg-slate-800 md:hidden">
              <div className="space-y-1 px-4 py-2">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700/50 hover:text-amber-400"
                  >
                    <span className="font-mono text-[9px] text-slate-500">{item.icon}</span>
                    <span>{item.label}</span>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}
        </nav>

        <main>{children}</main>

        <footer className="mt-8 border-t-4 border-slate-700 bg-slate-800/50 py-4">
          <div className="mx-auto max-w-7xl px-4 text-center">
            <p className="text-xs text-slate-500">CareerCraft - AI 驱动的职业模拟沙盒 | 2026</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
