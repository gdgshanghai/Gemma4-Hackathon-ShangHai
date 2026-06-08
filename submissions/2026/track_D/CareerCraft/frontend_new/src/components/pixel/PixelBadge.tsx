import React from 'react';
import { BADGE_VARIANTS, BadgeVariant } from '@/constants/designSystem';

type CompatibilityVariant = 
  | BadgeVariant 
  | 'honor' 
  | 'fun';

interface PixelBadgeProps {
  children: React.ReactNode;
  variant?: CompatibilityVariant;
  className?: string;
}

export default function PixelBadge({
  children,
  variant = 'neutral',
  className = '',
}: PixelBadgeProps) {
  const compatibleVariant: BadgeVariant = 
    variant === 'honor' ? 'warning' :
    variant === 'fun' ? 'success' :
    variant as BadgeVariant;

  const styles = BADGE_VARIANTS[compatibleVariant];

  return (
    <span
      className={`
        inline-block
        px-3 py-1
        text-sm font-bold
        border-2
        ${styles.bg}
        ${styles.text}
        ${styles.border}
        ${className}
      `}
      style={{
        boxShadow: `inset -2px -2px 0px 0px ${styles.shadowDark}, inset 2px 2px 0px 0px ${styles.shadowLight}`,
      }}
    >
      {children}
    </span>
  );
}
