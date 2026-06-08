import type { ReactNode } from 'react';

interface InventorySectionFrameProps {
  title?: string;
  rightAdornment?: ReactNode;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

export default function InventorySectionFrame({
  title,
  rightAdornment,
  className,
  contentClassName,
  children,
}: InventorySectionFrameProps) {
  return (
    <section
      className={[
        'relative overflow-hidden rounded-[1.75rem] border border-cyan-400/20',
        'bg-[#07111f]/70 backdrop-blur-xl',
        'shadow-[0_0_28px_rgba(34,211,238,0.12),inset_0_1px_0_rgba(255,255,255,0.04)]',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(250,204,21,0.08),transparent_24%),linear-gradient(180deg,rgba(255,255,255,0.05),transparent_22%,rgba(34,211,238,0.02)_100%)]" />
      <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/80 to-transparent" />
      <div className="pointer-events-none absolute inset-y-6 right-0 w-px bg-gradient-to-b from-transparent via-cyan-300/20 to-transparent" />

      {(title || rightAdornment) && (
        <div className="relative z-10 flex flex-wrap items-start justify-between gap-4 border-b border-white/5 px-5 py-4 sm:px-6">
          <div className="min-w-0 flex-1">
            {title && (
              <p className="font-mono text-[13px] uppercase tracking-[0.32em] text-cyan-300/90 sm:text-[14px] lg:text-[15px] break-words">
                {title}
              </p>
            )}
          </div>
          {rightAdornment ? <div className="relative z-10 shrink-0">{rightAdornment}</div> : null}
        </div>
      )}

      <div
        className={[
          'relative z-10 px-5 py-5 sm:px-6',
          contentClassName,
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {children}
      </div>
    </section>
  );
}
