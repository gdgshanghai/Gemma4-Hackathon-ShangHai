'use client';

import React from 'react';

interface PixelDialogProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

export default function PixelDialog({ open, onClose, title, children, footer, size = 'md' }: PixelDialogProps) {
  if (!open) return null;

  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-lg',
    lg: 'max-w-3xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/70"
        onClick={onClose}
      />
      <div
        className={`relative ${sizeClasses[size]} w-full mx-4 border-4 border-slate-600 bg-slate-900 p-6 max-h-[80vh] overflow-y-auto`}
        style={{
          boxShadow:
            'inset -4px -4px 0px 0px #020617, inset 4px 4px 0px 0px #334155, 0 0 0 4px #020617, 8px 8px 0 0 rgba(0,0,0,0.3)',
        }}
      >
        {title && (
          <div className="mb-4 pb-4 border-b-2 border-slate-700">
            <h2 className="text-xl font-bold text-amber-300">{title}</h2>
          </div>
        )}
        <div className="mb-4">{children}</div>
        {footer && (
          <div className="pt-4 border-t-2 border-slate-700">{footer}</div>
        )}
      </div>
    </div>
  );
}
