import React from 'react';
import PixelBadge from '@/components/pixel/PixelBadge';
import {
  StatusType,
  STATUS_CONFIG,
  getStatusBadgeVariant,
  getStatusLabel,
} from '@/constants/designSystem';

interface StatusBadgeProps {
  status: StatusType;
  showIcon?: boolean;
  className?: string;
}

export default function StatusBadge({
  status,
  showIcon = true,
  className = '',
}: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  const variant = getStatusBadgeVariant(status);
  const label = getStatusLabel(status);

  return (
    <PixelBadge variant={variant} className={className}>
      {showIcon && config.icon && <span className="mr-1">{config.icon}</span>}
      {label}
    </PixelBadge>
  );
}
