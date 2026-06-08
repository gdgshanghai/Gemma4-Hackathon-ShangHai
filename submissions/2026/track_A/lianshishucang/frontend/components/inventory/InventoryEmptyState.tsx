import { useTranslation } from 'react-i18next';
import InventorySectionFrame from './InventorySectionFrame';

interface InventoryEmptyStateProps {
  title: string;
  message: string;
}

export default function InventoryEmptyState({ title, message }: InventoryEmptyStateProps) {
  const { t } = useTranslation();
  return (
    <InventorySectionFrame className="h-full min-h-[260px]" contentClassName="flex h-full items-center">
      <div className="w-full text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/5 text-cyan-200 shadow-[0_0_18px_rgba(34,211,238,0.12)]">
          <span className="font-mono text-sm tracking-[0.28em]">{t('emptyState.null')}</span>
        </div>
        <h3 className="mt-6 text-lg font-semibold text-white">{title}</h3>
        <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-300/70">{message}</p>
      </div>
    </InventorySectionFrame>
  );
}
