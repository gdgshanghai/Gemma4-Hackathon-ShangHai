'use client';

import React from 'react';
import { useRouter } from 'next/navigation';

interface BackButtonProps {
  fallbackHref?: string;
  label?: string;
  className?: string;
}

export default function BackButton({
  fallbackHref = '/lobby',
  label = '返回',
  className = '',
}: BackButtonProps) {
  const router = useRouter();

  const handleBack = () => {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      router.back();
      return;
    }
    router.push(fallbackHref);
  };

  return (
    <button
      type="button"
      onClick={handleBack}
      className={`inline-flex min-h-10 items-center gap-2 border-2 border-slate-600 bg-slate-950/88 px-3 py-2 text-sm font-bold text-slate-200 shadow-[inset_-2px_-2px_0_#020617,inset_2px_2px_0_#475569] transition hover:-translate-y-0.5 hover:border-amber-500 hover:text-amber-300 ${className}`}
      aria-label={label}
    >
      <span aria-hidden="true" className="font-mono text-lg leading-none">←</span>
      <span>{label}</span>
    </button>
  );
}
