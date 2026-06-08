import React from 'react';

interface EvaluationStepProps {
  step: number;
  icon: string;
  title: string;
  description: string;
  isCompleted: boolean;
}

export default function EvaluationStepCard({
  step,
  icon,
  title,
  description,
  isCompleted,
}: EvaluationStepProps) {
  return (
    <div className="flex items-start gap-3 border-2 border-slate-700 bg-slate-900/70 p-3">
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center border-2 font-bold ${
          isCompleted
            ? 'border-emerald-500 bg-emerald-950/70 text-emerald-200'
            : 'border-slate-600 bg-slate-800 text-slate-300'
        }`}
      >
        {isCompleted ? '✓' : icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-xs font-bold text-amber-300">#{step}</span>
          <h4 className="text-sm font-bold text-slate-100">{title}</h4>
        </div>
        <p className="text-xs leading-5 text-slate-400">{description}</p>
      </div>
    </div>
  );
}
