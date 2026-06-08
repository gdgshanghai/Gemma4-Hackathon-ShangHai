import { useTranslation } from 'react-i18next';
import { BriefcaseBusiness, Wallet2 } from 'lucide-react';

interface InventoryBottomNavProps {
  activeTab: 'wallet' | 'business';
  onChange: (tab: 'wallet' | 'business') => void;
}

export default function InventoryBottomNav({
  activeTab,
  onChange,
}: InventoryBottomNavProps) {
  const { t } = useTranslation();
  const items = [
    {
      key: 'business' as const,
      label: t('nav.business'),
      Icon: BriefcaseBusiness,
    },
    {
      key: 'wallet' as const,
      label: t('nav.wallet'),
      Icon: Wallet2,
    },
  ];
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
      <div className="pointer-events-auto flex gap-3 rounded-full border border-cyan-400/20 bg-[#06111c]/85 px-4 py-3 shadow-[0_0_28px_rgba(34,211,238,0.12)] backdrop-blur-xl">
        {items.map(({ key, label, Icon }) => {
          const isActive = key === activeTab;
          return (
            <button
              key={key}
              type="button"
              onClick={() => onChange(key)}
              className={[
                'flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition',
                isActive
                  ? 'border-cyan-300/35 bg-cyan-300/10 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.18)]'
                  : 'border-white/8 bg-white/5 text-slate-300/75 hover:border-cyan-300/20 hover:text-white',
              ].join(' ')}
            >
              <Icon size={16} />
              <span className="font-medium">{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
