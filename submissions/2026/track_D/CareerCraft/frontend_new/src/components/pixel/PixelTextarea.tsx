'use client';

import React from 'react';

interface PixelTextareaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  className?: string;
  disabled?: boolean;
}

export default function PixelTextarea({
  value,
  onChange,
  placeholder,
  rows = 4,
  className = '',
  disabled = false,
}: PixelTextareaProps) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      disabled={disabled}
      className={`
        w-full
        p-4
        bg-slate-900
        text-slate-200
        border-4
        border-slate-600
        focus:border-indigo-500
        outline-none
        resize-y
        font-mono
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
      style={{
        boxShadow:
          'inset -2px -2px 0px 0px #0f172a, inset 2px 2px 0px 0px #475569',
      }}
    />
  );
}
