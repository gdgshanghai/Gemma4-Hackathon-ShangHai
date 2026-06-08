import { useTranslation } from 'react-i18next';
import {
  CARD_FILTER_OPTIONS,
  LIFECYCLE_FILTER_OPTIONS,
  SORT_OPTIONS,
} from '../../lib/inventory/constants';
import type {
  InventoryCardFilterStatus,
  InventoryFilterStatus,
  InventorySortBy,
} from '../../types/inventory';
import InventorySectionFrame from './InventorySectionFrame';

interface InventoryToolbarProps {
  searchQuery: string;
  statusFilter: InventoryFilterStatus;
  cardFilter: InventoryCardFilterStatus;
  sortBy: InventorySortBy;
  resultCount: number;
  onSearchQueryChange: (value: string) => void;
  onStatusFilterChange: (value: InventoryFilterStatus) => void;
  onCardFilterChange: (value: InventoryCardFilterStatus) => void;
  onSortByChange: (value: InventorySortBy) => void;
}

export default function InventoryToolbar({
  searchQuery,
  statusFilter,
  cardFilter,
  sortBy,
  resultCount,
  onSearchQueryChange,
  onStatusFilterChange,
  onCardFilterChange,
  onSortByChange,
}: InventoryToolbarProps) {
  const { t } = useTranslation();
  return (
    <InventorySectionFrame
      title={t('toolbar.title')}
      rightAdornment={
        <div className="rounded-full border border-cyan-300/15 bg-cyan-300/8 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-100/80">
          {t('toolbar.unitsVisible', { count: resultCount })}
        </div>
      }
      contentClassName="space-y-5"
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_repeat(2,minmax(0,1fr))]">
        <label className="block">
          <span className="mb-2 block font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
            {t('toolbar.searchSignal')}
          </span>
          <input
            value={searchQuery}
            onChange={(event) => onSearchQueryChange(event.target.value)}
            placeholder={t('toolbar.searchPlaceholder')}
            className="w-full rounded-2xl border border-cyan-400/15 bg-[#071523]/80 px-4 py-3 text-base text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/45 focus:shadow-[0_0_0_1px_rgba(103,232,249,0.2)]"
          />
        </label>

        <SelectField
          label={t('toolbar.lifecycle')}
          value={statusFilter}
          options={LIFECYCLE_FILTER_OPTIONS}
          onChange={(value) => onStatusFilterChange(value as InventoryFilterStatus)}
        />
        <SelectField
          label={t('toolbar.cardPipeline')}
          value={cardFilter}
          options={CARD_FILTER_OPTIONS}
          onChange={(value) => onCardFilterChange(value as InventoryCardFilterStatus)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <SelectField
          label={t('toolbar.sortMode')}
          value={sortBy}
          options={SORT_OPTIONS}
          onChange={(value) => onSortByChange(value as InventorySortBy)}
        />

        <div>
          <span className="mb-2 block font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
            {t('toolbar.quickFilters')}
          </span>
          <div className="flex flex-wrap gap-2">
            {LIFECYCLE_FILTER_OPTIONS.slice(1, 5).map((option) => {
              const isActive = option.value === statusFilter;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onStatusFilterChange(option.value)}
                  className={[
                    'rounded-full border px-3 py-2 text-sm font-medium transition',
                    isActive
                      ? 'border-cyan-300/35 bg-cyan-300/10 text-cyan-100 shadow-[0_0_16px_rgba(34,211,238,0.18)]'
                      : 'border-white/8 bg-white/5 text-slate-300/70 hover:border-cyan-300/20 hover:text-white',
                  ].join(' ')}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </InventorySectionFrame>
  );
}

interface SelectFieldProps {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}

function SelectField({ label, value, options, onChange }: SelectFieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-cyan-400/15 bg-[#071523]/80 px-4 py-3 text-base text-white outline-none focus:border-cyan-300/45 focus:shadow-[0_0_0_1px_rgba(103,232,249,0.2)]"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
