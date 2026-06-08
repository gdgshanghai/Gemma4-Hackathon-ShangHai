import React from 'react';

interface PixelCardProps {
  children: React.ReactNode;
  title?: string;
  className?: string;
  hoverable?: boolean;
}

export default function PixelCard(props: PixelCardProps) {
  const { children, title, className, hoverable = false } = props;
  
  let combinedClassName = 'pixel-card-unified bg-slate-800 border-4 border-slate-600 p-5';
  if (hoverable) {
    combinedClassName += ' transition-all hover:border-slate-500 cursor-pointer';
  }
  if (className) {
    combinedClassName = combinedClassName + ' ' + className;
  }

  return (
    <div
      className={combinedClassName}
      style={{
        boxShadow: 'inset -4px -4px 0px 0px #0f172a, inset 4px 4px 0px 0px #475569',
      }}
    >
      {title ? (
        <h3 className="pixel-title text-amber-400 font-bold text-lg mb-4 pb-2 border-b-2 border-amber-700/60">
          {title}
        </h3>
      ) : null}
      {children}
    </div>
  );
}
