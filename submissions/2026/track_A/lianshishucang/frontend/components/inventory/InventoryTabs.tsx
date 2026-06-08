import { useTranslation } from 'react-i18next';

interface InventoryTabsProps {
  activeTab: 'wallet' | 'business';
  onChange: (tab: 'wallet' | 'business') => void;
}

export default function InventoryTabs({ activeTab, onChange }: InventoryTabsProps) {
  const { t } = useTranslation();
  const tabs = [
    {
      key: 'business' as const,
      label: t('nav.business'),
    },
    {
      key: 'wallet' as const,
      label: t('nav.wallet'),
    },
  ];
  return (
    <div className="rounded-[1.5rem] border border-cyan-400/15 bg-[#06111c]/70 p-3 backdrop-blur-lg shadow-[0_0_24px_rgba(34,211,238,0.08)]">
      <div role="tablist" aria-label={t('nav.inventoryWorkspaceViews')} className="flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const isActive = tab.key === activeTab;
          const tabId = `inventory-tab-${tab.key}`;
          const panelId = `inventory-panel-${tab.key}`;

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
