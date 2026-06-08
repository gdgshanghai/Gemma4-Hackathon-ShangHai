'use client';

import React from 'react';
import { BUTTON_VARIANTS } from '@/constants/designSystem';

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

interface PixelButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: ButtonVariant;
  className?: string;
  fullWidth?: boolean;
}

export default function PixelButton({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  className = '',
  fullWidth = false,
}: PixelButtonProps) {
  const styles = BUTTON_VARIANTS[variant];

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        relative
        px-6 py-3
        font-bold
        cursor-pointer
        transition-transform
        select-none
        ${styles.bg}
        ${styles.text}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
      style={{
        boxShadow: disabled
          ? 'inset 4px 4px 0px 0px #374151'
          : styles.shadowDark !== 'none'
          ? `inset -4px -4px 0px 0px ${styles.shadowDark}, inset 4px 4px 0px 0px ${styles.shadowLight}`
          : 'none',
      }}
      onMouseDown={(e) => {
        if (!disabled && e.button === 0) {
          e.currentTarget.style.transform = 'translateY(2px)';
          if (styles.shadowDark !== 'none') {
            e.currentTarget.style.boxShadow = disabled
              ? 'inset 4px 4px 0px 0px #374151'
              : `inset 4px 4px 0px 0px ${styles.shadowLight}, inset -4px -4px 0px 0px ${styles.shadowDark}`;
          }
        }
      }}
      onMouseUp={(e) => {
        if (!disabled && e.button === 0) {
          e.currentTarget.style.transform = '';
          if (styles.shadowDark !== 'none') {
            e.currentTarget.style.boxShadow = disabled
              ? 'inset 4px 4px 0px 0px #374151'
              : `inset -4px -4px 0px 0px ${styles.shadowDark}, inset 4px 4px 0px 0px ${styles.shadowLight}`;
          }
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = '';
        if (styles.shadowDark !== 'none') {
          e.currentTarget.style.boxShadow = disabled
            ? 'inset 4px 4px 0px 0px #374151'
            : `inset -4px -4px 0px 0px ${styles.shadowDark}, inset 4px 4px 0px 0px ${styles.shadowLight}`;
        }
      }}
    >
      {children}
    </button>
  );
}
