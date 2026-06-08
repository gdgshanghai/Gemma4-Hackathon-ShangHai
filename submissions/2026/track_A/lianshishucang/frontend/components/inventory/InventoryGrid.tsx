import { motion } from 'framer-motion';
import InventorySlot from '../InventorySlot';
import { ACCENT_STYLES } from '../../lib/inventory/constants';
import type { InventoryItemViewModel } from '../../types/inventory';
import InventoryEmptyState from './InventoryEmptyState';
import { useTranslation } from 'react-i18next';
import InventorySectionFrame from './InventorySectionFrame';

interface InventoryGridProps {
  items: InventoryItemViewModel[];
  selectedId?: string;
  onSelect: (itemId: string) => void;
}

export default function InventoryGrid({ items, selectedId, onSelect }: InventoryGridProps) {
  const { t } = useTranslation();
  if (!items.length) {
    return <InventoryEmptyState title={t('grid.noResults')} message={t('grid.noItems')} />;
  }

  return (
    <InventorySectionFrame title={t('grid.title')} contentClassName="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {items.map((item, index) => {
          const isSelected = item.id === selectedId;
          const accent = ACCENT_STYLES[item.accentTone];

          return (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.28, delay: index * 0.03, ease: 'easeOut' }}
              className={[
                'rounded-[1.6rem] border bg-[#09131f]/70 p-3 backdrop-blur-lg',
                isSelected
                  ? `border-yellow-300/30 shadow-[0_0_26px_rgba(250,204,21,0.16)] ${accent.ring} ring-1`
                  : 'border-cyan-400/10 shadow-[0_0_20px_rgba(34,211,238,0.06)]',
              ].join(' ')}
            >
              <InventorySlot
                id={item.displayCode}
                imageUrl={item.imageUrl}
                name={item.name}
                isSelected={isSelected}
                onClick={() => onSelect(item.id)}
              />

              <div className="mt-3 space-y-3 px-1 pb-1">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate text-base font-medium text-white">{item.name}</h3>
                    <p className="mt-1 truncate text-sm text-slate-400">{item.physicalLocation ?? '—'}</p>
                  </div>
                  <span
                    className={[
                      'rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em]',
                      accent.badge,
                    ].join(' ')}
                  >
                    {item.statusLabel}
                  </span>
                </div>

                <div className="flex flex-wrap gap-2">
                  <span
                    className={[
                      'rounded-full border px-2.5 py-1 text-[11px] uppercase tracking-[0.18em]',
                      accent.softBadge,
                    ].join(' ')}
                  >
                    {item.cardStatusLabel}
                  </span>
                  {item.attributes.slice(0, 2).map((attribute) => (
                    <span
                      key={`${item.id}-${attribute.trait_type}`}
                      className="rounded-full border border-white/8 bg-white/5 px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] text-slate-300/85"
                    >
                      {attribute.trait_type}: {attribute.value}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </InventorySectionFrame>
  );
}
