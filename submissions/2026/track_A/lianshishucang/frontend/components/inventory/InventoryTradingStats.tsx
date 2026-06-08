import { useTranslation } from 'react-i18next';
import InventorySectionFrame from './InventorySectionFrame';
import type { InventoryItemViewModel } from '../../types/inventory';

interface InventoryTradingStatsProps {
  items: InventoryItemViewModel[];
}

export default function InventoryTradingStats({ items }: InventoryTradingStatsProps) {
  const { t } = useTranslation();
  const stats = [
    {
      label: t('tradingStats.totalCollectibles'),
      value: items.length,
    },
    {
      label: t('tradingStats.cardReady'),
      value: items.filter((item) => item.hasGeneratedCard).length,
    },
    {
      label: t('tradingStats.mintPrepared'),
      value: items.filter((item) => item.hasMintPrep).length,
    },
    {
      label: t('tradingStats.minted'),
      value: items.filter((item) => item.status === 'minted').length,
    },
    {
      label: t('tradingStats.nftLinked'),
      value: items.filter((item) => Boolean(item.nftId)).length,
    },
  ];

  return (
    <InventorySectionFrame title={t('tradingStats.title')} contentClassName="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-[1.35rem] border border-cyan-400/12 bg-[#08131f]/75 p-4 shadow-[0_0_18px_rgba(34,211,238,0.06)]"
        >
          <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan-300/65">
            {stat.label}
          </p>
          <p className="mt-3 text-3xl font-semibold text-white">{stat.value}</p>
        </div>
      ))}
    </InventorySectionFrame>
  );
}
