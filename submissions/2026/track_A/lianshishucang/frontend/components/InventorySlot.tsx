'use client';

import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import type { KeyboardEvent } from 'react';

interface InventorySlotProps {
  id: string;
  imageUrl: string;
  name: string;
  isSelected: boolean;
  onClick: () => void;
}

export default function InventorySlot({
  id,
  imageUrl,
  name,
  isSelected,
  onClick,
}: InventorySlotProps) {
  const { t } = useTranslation();
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onClick();
    }
  };

  return (
    <motion.div
      role="button"
      tabIndex={0}
      title={name}
      aria-label={t('grid.ariaLabel', { name, id })}
      aria-pressed={isSelected}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      whileHover={{ scale: isSelected ? 1.06 : 1.05 }}
      whileTap={{ scale: 0.95 }}
      animate={{ scale: isSelected ? 1.02 : 1 }}
      transition={{ type: 'spring', stiffness: 320, damping: 24, mass: 0.7 }}
      className={[
        'group relative aspect-square w-full cursor-pointer overflow-hidden rounded-2xl',
        'border bg-[#0a192f]/40 backdrop-blur-md',
        isSelected
          ? 'border-yellow-400/90 shadow-[0_0_22px_rgba(250,204,21,0.45),inset_0_0_18px_rgba(250,204,21,0.12)]'
          : 'border-cyan-500/30 hover:border-cyan-400/90 hover:shadow-[0_0_18px_rgba(34,211,238,0.4),inset_0_0_18px_rgba(34,211,238,0.08)]',
        'transition-shadow duration-200',
      ].join(' ')}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(103,232,249,0.18),transparent_42%),linear-gradient(180deg,rgba(255,255,255,0.06),transparent_30%,rgba(34,211,238,0.04)_100%)]" />
      <div className="pointer-events-none absolute inset-x-3 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/70 to-transparent" />
      <div className="pointer-events-none absolute inset-y-3 left-0 w-px bg-gradient-to-b from-transparent via-cyan-300/40 to-transparent" />
      <div className="pointer-events-none absolute right-2 top-2 h-6 w-6 rounded-tr-xl border-r border-t border-cyan-300/30" />

      {isSelected && (
        <motion.div
          className="pointer-events-none absolute inset-0 rounded-2xl border border-yellow-300/50"
          animate={{
            opacity: [0.45, 0.95, 0.45],
            boxShadow: [
              '0 0 18px rgba(250,204,21,0.18), inset 0 0 12px rgba(250,204,21,0.06)',
              '0 0 30px rgba(250,204,21,0.38), inset 0 0 18px rgba(250,204,21,0.14)',
              '0 0 18px rgba(250,204,21,0.18), inset 0 0 12px rgba(250,204,21,0.06)',
            ],
          }}
          transition={{
            duration: 2.2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}

      <div className="absolute left-3 top-3 z-20 font-mono text-[10px] uppercase tracking-[0.28em] text-cyan-400/70">
        {id}
      </div>

      <div className="relative z-10 flex h-full w-full items-center justify-center p-4 sm:p-5">
        <img
          src={imageUrl}
          alt={name}
          draggable={false}
          className="h-full w-full object-contain select-none drop-shadow-[0_0_14px_rgba(125,211,252,0.18)]"
        />
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-cyan-400/10 to-transparent" />
    </motion.div>
  );
}
