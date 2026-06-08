'use client';

import React from 'react';

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '6xl' | '7xl';
}

export default function PageContainer({ 
  children, 
  className = '',
  maxWidth = '7xl'
}: PageContainerProps) {
  const maxWidthClasses = {
    'sm': 'max-w-sm',
    'md': 'max-w-md',
    'lg': 'max-w-lg',
    'xl': 'max-w-xl',
    '6xl': 'max-w-6xl',
    '7xl': 'max-w-7xl'
  };

  return (
    <main className={`${maxWidthClasses[maxWidth]} pixel-page-shell mx-auto px-4 py-6 ${className}`}>
      {children}
    </main>
  );
}
