import { useTranslation } from 'react-i18next';

interface InventoryBusinessTabsProps {
  activeTab: 'collection' | 'trading';
  onChange: (tab: 'collection' | 'trading') => void;
}

export default function InventoryBusinessTabs({
  activeTab,
  onChange,
}: InventoryBusinessTabsProps) {
  const { t } = useTranslation();
  const tabs = [
    {
      key: 'collection' as const,
      label: t('nav.collection'),
    },
    {
      key: 'trading' as const,
      label: t('nav.nftTrading'),
    },
  ];
  return (
    <div className="rounded-[1.5rem] border border-cyan-400/15 bg-[#06111c]/60 p-3 backdrop-blur-lg shadow-[0_0_24px_rgba(34,211,238,0.08)]">
      <div role="tablist" aria-label={t('nav.businessWorkspaceViews')} className="flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const isActive = tab.key === activeTab;
          const tabId = `business-tab-${tab.key}`;
          const panelId = `business-panel-${tab.key}`;

          return (
            <button
              key={tab.key}
              id={tabId}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={panelId}
              tabIndex={isActive ? 0 : -1}
              onClick={() => onChange(tab.key)}
              className={[
                'rounded-full border px-4 py-2.5 text-left transition outline-none',
                'focus-visible:ring-2 focus-visible:ring-cyan-300/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[#06111c]',
                isActive
                  ? 'border-cyan-300/35 bg-cyan-300/10 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.18)]'
                  : 'border-white/8 bg-white/5 text-slate-300/75 hover:border-cyan-300/20 hover:text-white',
              ].join(' ')}
            >
              <span className="block font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65 sm:text-[12px]">
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
