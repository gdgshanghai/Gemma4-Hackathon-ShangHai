import { motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import type { InventoryDataSource, InventoryItemViewModel } from '../../types/inventory';

interface InventoryHeaderProps {
  selectedItem?: InventoryItemViewModel;
  dataSource: InventoryDataSource;
}

export default function InventoryHeader({ selectedItem, dataSource }: InventoryHeaderProps) {
  const { t } = useTranslation();
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: 'easeOut' }}
      className="relative overflow-hidden rounded-[2rem] border border-cyan-400/20 bg-[#071423]/80 p-6 shadow-[0_0_30px_rgba(34,211,238,0.12)] backdrop-blur-xl sm:p-8"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.18),transparent_35%),linear-gradient(135deg,rgba(255,255,255,0.05),transparent_35%,rgba(34,211,238,0.04)_100%)]" />

      <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl min-w-0 flex-1">
          <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-[2.7rem] break-words">
            {t('header.title')}
          </h1>
        </div>

        <div className="rounded-2xl border border-cyan-400/15 bg-[#0b1a2a]/70 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] shrink-0 max-w-full lg:max-w-[320px]">
          <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-cyan-300/60">
            {dataSource.toUpperCase()}
          </p>
          <p className="mt-2 text-xl font-medium text-white sm:text-2xl break-words">
            {selectedItem?.name ?? '—'}
          </p>
          <p className="mt-1 text-base text-slate-300/65 break-all">
            {selectedItem?.displayCode ?? '—'}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
