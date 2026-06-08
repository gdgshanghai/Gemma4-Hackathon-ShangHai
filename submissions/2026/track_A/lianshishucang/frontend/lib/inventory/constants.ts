import i18n from '../../lib/i18n/i18n';
import type {
  InventoryAccentTone,
  InventoryCardFilterStatus,
  InventoryCardStatus,
  InventoryFilterOption,
  InventoryFilterStatus,
  InventoryLifecycleStatus,
  InventorySortBy,
} from '../../types/inventory';

export const STATUS_LABELS: Record<InventoryLifecycleStatus, string> = {
  pending_ai: i18n.t('status.pendingAi'),
  stored: i18n.t('status.stored'),
  failed: i18n.t('status.flagged'),
  awaiting_mint: i18n.t('status.pendingMint'),
  minted: i18n.t('status.minted'),
  shipped: i18n.t('status.archived'),
};

export const CARD_STATUS_LABELS: Record<InventoryCardStatus, string> = {
  pending: i18n.t('status.cardPending'),
  generating: i18n.t('status.rendering'),
  completed: i18n.t('status.cardReady'),
  failed: i18n.t('status.renderFailed'),
};

export const STATUS_ACCENTS: Record<InventoryLifecycleStatus, InventoryAccentTone> = {
  pending_ai: 'purple',
  stored: 'cyan',
  failed: 'red',
  awaiting_mint: 'yellow',
  minted: 'green',
  shipped: 'purple',
};

export const LIFECYCLE_FILTER_OPTIONS: InventoryFilterOption<InventoryFilterStatus>[] = [
  { value: 'all', label: i18n.t('status.allStates') },
  { value: 'stored', label: i18n.t('status.stored') },
  { value: 'awaiting_mint', label: i18n.t('status.pendingMint') },
  { value: 'minted', label: i18n.t('status.minted') },
  { value: 'failed', label: i18n.t('status.flagged') },
  { value: 'pending_ai', label: i18n.t('status.pendingAi') },
  { value: 'shipped', label: i18n.t('status.archived') },
];

export const CARD_FILTER_OPTIONS: InventoryFilterOption<InventoryCardFilterStatus>[] = [
  { value: 'all', label: i18n.t('status.allCards') },
  { value: 'pending', label: i18n.t('common.pending') },
  { value: 'generating', label: i18n.t('status.rendering') },
  { value: 'completed', label: i18n.t('common.ready') },
  { value: 'failed', label: i18n.t('common.failed') },
];

export const SORT_OPTIONS: InventoryFilterOption<InventorySortBy>[] = [
  { value: 'updated_desc', label: i18n.t('status.sortRecentlyUpdated') },
  { value: 'created_desc', label: i18n.t('status.sortNewestAdded') },
  { value: 'name_asc', label: i18n.t('status.sortNameAZ') },
  { value: 'status', label: i18n.t('status.sortStatusMatrix') },
];

export const ACCENT_STYLES: Record<
  InventoryAccentTone,
  {
    badge: string;
    softBadge: string;
    text: string;
    ring: string;
  }
> = {
  cyan: {
    badge: 'border-cyan-400/40 bg-cyan-400/10 text-cyan-200',
    softBadge: 'border-cyan-500/20 bg-cyan-500/5 text-cyan-100/80',
    text: 'text-cyan-200',
    ring: 'ring-cyan-400/40',
  },
  yellow: {
    badge: 'border-yellow-300/40 bg-yellow-300/10 text-yellow-100',
    softBadge: 'border-yellow-400/20 bg-yellow-400/5 text-yellow-100/80',
    text: 'text-yellow-100',
    ring: 'ring-yellow-300/40',
  },
  red: {
    badge: 'border-rose-400/40 bg-rose-400/10 text-rose-100',
    softBadge: 'border-rose-400/20 bg-rose-400/5 text-rose-100/80',
    text: 'text-rose-100',
    ring: 'ring-rose-400/40',
  },
  purple: {
    badge: 'border-fuchsia-400/40 bg-fuchsia-400/10 text-fuchsia-100',
    softBadge: 'border-fuchsia-400/20 bg-fuchsia-400/5 text-fuchsia-100/80',
    text: 'text-fuchsia-100',
    ring: 'ring-fuchsia-400/40',
  },
  green: {
    badge: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-100',
    softBadge: 'border-emerald-400/20 bg-emerald-400/5 text-emerald-100/80',
    text: 'text-emerald-100',
    ring: 'ring-emerald-400/40',
  },
};
