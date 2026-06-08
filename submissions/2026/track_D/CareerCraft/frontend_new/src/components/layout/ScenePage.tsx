import React from 'react';
import PageContainer from './PageContainer';

interface ScenePageProps {
  children: React.ReactNode;
  backgroundImage: string;
  className?: string;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '6xl' | '7xl';
  position?: string;
}

export default function ScenePage({
  children,
  backgroundImage,
  className = '',
  maxWidth = '7xl',
  position = 'center top',
}: ScenePageProps) {
  return (
    <div
      className={`relative min-h-screen bg-slate-950 text-slate-100 ${className}`}
      style={{
        backgroundImage: `linear-gradient(180deg, rgba(2,6,23,0.84) 0%, rgba(2,6,23,0.64) 42%, rgba(2,6,23,0.93) 100%), url(${backgroundImage})`,
        backgroundSize: 'cover',
        backgroundPosition: position,
        backgroundAttachment: 'fixed',
      }}
    >
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.024)_1px,transparent_1px)] bg-[length:100%_5px] opacity-45" />
      <PageContainer maxWidth={maxWidth}>
        <div className="relative z-10">{children}</div>
      </PageContainer>
    </div>
  );
}
