'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { motion } from 'framer-motion';
import { ACCENT_STYLES } from '../../lib/inventory/constants';
import type { InventoryItemViewModel } from '../../types/inventory';
import InventoryEmptyState from './InventoryEmptyState';
import InventorySectionFrame from './InventorySectionFrame';

interface InventoryDetailPanelProps {
  item?: InventoryItemViewModel;
}

export default function InventoryDetailPanel({ item }: InventoryDetailPanelProps) {
  const { t } = useTranslation();
  const [activePanel, setActivePanel] = useState<'overview' | 'attributes' | 'lifecycle'>('overview');

  if (!item) {
    return <InventoryEmptyState title={t('detailPanel.noUnitSelected')} message={t('detailPanel.noData')} />;
  }

  const accent = ACCENT_STYLES[item.accentTone];
  const timeline = [
    { label: t('detailPanel.uploadIndexed'), active: true },
    { label: t('detailPanel.aiIdentified'), active: item.status !== 'pending_ai' },
    { label: t('detailPanel.cardRendered'), active: item.cardGenerationStatus === 'completed' },
    { label: t('detailPanel.mintPrepared'), active: item.hasMintPrep },
    { label: t('detailPanel.minted'), active: item.status === 'minted' || item.status === 'shipped' },
  ];

  return (
    <InventorySectionFrame title={t('detailPanel.title')} contentClassName="space-y-6">
      <div className="grid gap-6">
        <motion.div
          key={item.id}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut' }}
          className="relative overflow-hidden rounded-[1.75rem] border border-cyan-400/15 bg-[#08131f]/80 p-4"
        >
          {item.aigcBackgroundUrl ? (
            <div
              className="absolute inset-0 bg-cover bg-center opacity-25"
              style={{ backgroundImage: `url(${item.aigcBackgroundUrl})` }}
            />
          ) : null}
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(7,17,31,0.05),rgba(7,17,31,0.84))]" />

          <div className="relative z-10 space-y-4">
            <div className="overflow-hidden rounded-[1.5rem] border border-white/10 bg-[#06111b]/60 p-4 shadow-[0_0_24px_rgba(34,211,238,0.08)]">
              <img
                src={item.virtualCardUrl || item.imageUrl}
                alt={item.name}
                className="h-72 w-full object-contain sm:h-80"
              />
            </div>

            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[12px] uppercase tracking-[0.28em] text-cyan-300/75 sm:text-[13px]">
                  {item.displayCode}
                </p>
                <h2 className="mt-2 text-[2rem] font-semibold leading-tight text-white sm:text-[2.15rem]">
                  {item.name}
                </h2>
                <p className="mt-2 text-base text-slate-300/70">
                  {item.physicalLocation ?? t('common.none')}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <span
                  className={[
                    'rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-[0.18em]',
                    accent.badge,
                  ].join(' ')}
                >
                  {item.statusLabel}
                </span>
                <span
                  className={[
                    'rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-[0.18em]',
                    accent.softBadge,
                  ].join(' ')}
                >
                  {item.cardStatusLabel}
                </span>
              </div>
            </div>
          </div>
        </motion.div>

        <div className="grid gap-4 sm:grid-cols-2">
          <StatCard
            label={t('detailPanel.royaltyFee')}
            value={item.royaltyFee ? `${(item.royaltyFee / 100).toFixed(2)}%` : t('common.none')}
          />
          <StatCard label={t('detailPanel.mintSignal')} value={item.hasMintPrep ? t('detailPanel.prepared') : t('detailPanel.awaiting')} />
          <StatCard label={t('detailPanel.linkedNft')} value={item.nftName ?? t('detailPanel.unlinked')} />
          <StatCard label={t('detailPanel.tokenUri')} value={truncateMiddle(item.tokenUri ?? t('common.unavailable'), 26)} />
        </div>

        <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
          <div className="flex flex-wrap gap-2">
            <PanelTab
              label={t('detailPanel.overview')}
              active={activePanel === 'overview'}
              onClick={() => setActivePanel('overview')}
            />
            <PanelTab
              label={t('detailPanel.attributes')}
              active={activePanel === 'attributes'}
              onClick={() => setActivePanel('attributes')}
            />
            <PanelTab
              label={t('detailPanel.lifecycle')}
              active={activePanel === 'lifecycle'}
              onClick={() => setActivePanel('lifecycle')}
            />
          </div>

          <div className="mt-4 max-h-[520px] overflow-y-auto pr-2 [scrollbar-color:rgba(103,232,249,0.45)_transparent] [scrollbar-width:thin]">
            {activePanel === 'overview' ? (
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-[1.35rem] border border-cyan-400/12 bg-[#08131f]/75 p-4">
                  <p className="font-mono text-[12px] uppercase tracking-[0.24em] text-cyan-300/70 sm:text-[13px]">
                    {t('detailPanel.assetSummary')}
                  </p>
                  <dl className="mt-4 space-y-3 text-base">
                    <Row label={t('detailPanel.collection')} value={item.displayCode} />
                    <Row label={t('detailPanel.status')} value={item.statusLabel} />
                    <Row label={t('detailPanel.card')} value={item.cardStatusLabel} />
                    <Row label={t('detailPanel.location')} value={item.physicalLocation ?? t('common.none')} />
                    <Row label={t('detailPanel.tokenUri')} value={truncateMiddle(item.tokenUri ?? t('common.unavailable'), 28)} />
                  </dl>
                </div>
                <div className="rounded-[1.35rem] border border-cyan-400/12 bg-[#08131f]/75 p-4">
                  <p className="font-mono text-[12px] uppercase tracking-[0.24em] text-cyan-300/70 sm:text-[13px]">
                    {t('detailPanel.nftSummary')}
                  </p>
                  <dl className="mt-4 space-y-3 text-base">
                    <Row label={t('detailPanel.linkedNft')} value={item.nftName ?? t('detailPanel.unlinked')} />
                    <Row label={t('detailPanel.royalty')} value={item.royaltyFee ? `${(item.royaltyFee / 100).toFixed(2)}%` : t('common.none')} />
                    <Row label={t('detailPanel.created')} value={formatDate(item.createdAt)} />
                    <Row label={t('detailPanel.updated')} value={formatDate(item.updatedAt)} />
                    <Row label={t('detailPanel.mintPrep')} value={item.hasMintPrep ? t('detailPanel.prepared') : t('common.pending')} />
                  </dl>
                </div>
              </div>
            ) : null}

            {activePanel === 'attributes' ? (
              <div>
                  <p className="font-mono text-[12px] uppercase tracking-[0.26em] text-cyan-300/70 sm:text-[13px]">
                    {t('detailPanel.attributeMatrix')}
                  </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {item.attributes.length ? (
                    item.attributes.map((attribute) => (
                      <div
                        key={`${item.id}-${attribute.trait_type}`}
                        className="min-w-[150px] max-w-full rounded-[1.5rem] border border-cyan-400/15 bg-cyan-400/5 px-4 py-3 text-base text-slate-100"
                      >
                        <span className="block text-cyan-200/75">{attribute.trait_type}</span>
                        <span className="mt-2 block break-words text-white">{attribute.value}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-base text-slate-400">—</p>
                  )}
                </div>
              </div>
            ) : null}

            {activePanel === 'lifecycle' ? (
              <div>
                  <p className="font-mono text-[12px] uppercase tracking-[0.26em] text-cyan-300/70 sm:text-[13px]">
                    {t('detailPanel.lifecycleChain')}
                  </p>
                <div className="mt-4 space-y-4">
                  {timeline.map((step) => (
                    <div key={step.label} className="flex items-center gap-4">
                      <span
                        className={[
                          'h-3 w-3 shrink-0 rounded-full',
                          step.active ? 'bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,0.8)]' : 'bg-slate-600',
                        ].join(' ')}
                      />
                      <span className={step.active ? 'text-lg text-white' : 'text-lg text-slate-500'}>
                        {step.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </InventorySectionFrame>
  );
}

function PanelTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-full border px-3 py-2 text-sm font-medium transition',
        active
          ? 'border-cyan-300/35 bg-cyan-300/10 text-cyan-100 shadow-[0_0_16px_rgba(34,211,238,0.18)]'
          : 'border-white/8 bg-white/5 text-slate-300/70 hover:border-cyan-300/20 hover:text-white',
      ].join(' ')}
    >
      {label}
    </button>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/6 pb-2">
      <dt className="text-cyan-200/75">{label}</dt>
      <dd className="max-w-[60%] break-words text-right text-white">{value}</dd>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string;
}

function StatCard({ label, value }: StatCardProps) {
  return (
    <div className="rounded-[1.35rem] border border-white/8 bg-white/5 p-4">
      <p className="font-mono text-[12px] uppercase tracking-[0.26em] text-cyan-300/65 sm:text-[13px]">{label}</p>
      <p className="mt-3 text-lg font-medium break-all text-white sm:text-xl">{value}</p>
    </div>
  );
}

function truncateMiddle(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }

  const prefixLength = Math.ceil((maxLength - 3) / 2);
  const suffixLength = Math.floor((maxLength - 3) / 2);
  return `${value.slice(0, prefixLength)}...${value.slice(-suffixLength)}`;
}

function formatDate(value?: string): string {
  if (!value) {
    return '—';
  }

  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(parsed));
}
