import { useTranslation } from 'react-i18next';
import type {
  InventoryActionKind,
  InventoryActionNotice,
  InventoryDataSource,
  InventoryItemViewModel,
} from '../../types/inventory';
import InventorySectionFrame from './InventorySectionFrame';

interface InventoryItemActionsProps {
  selectedItem?: InventoryItemViewModel;
  onRefresh: () => void;
  onGenerateCard: (collectionId: number) => void;
  onPrepareMint: (collectionId: number) => void;
  onViewTokenUri: (tokenUri?: string) => void;
  onMintNFT?: () => Promise<void>;
  actionState?: {
    kind: InventoryActionKind;
    collectionId?: number;
  } | null;
  notice?: InventoryActionNotice | null;
  dataSource: InventoryDataSource;
}

export default function InventoryItemActions({
  selectedItem,
  onRefresh,
  onGenerateCard,
  onPrepareMint,
  onViewTokenUri,
  onMintNFT,
  actionState,
  notice,
  dataSource,
}: InventoryItemActionsProps) {
  const { t } = useTranslation();
  const isSelectedActionRunning =
    actionState?.collectionId && selectedItem?.collectionId === actionState.collectionId;

  const actionItems = [
    {
      label: actionState?.kind === 'refresh' ? t('itemActions.refreshing') : t('itemActions.refreshGrid'),
      enabled: !actionState,
      accent: 'cyan',
      onClick: onRefresh,
    },
    {
      label:
        actionState?.kind === 'generate_card' && isSelectedActionRunning
          ? t('itemActions.renderingCard')
          : t('itemActions.generateCard'),
      enabled:
        Boolean(selectedItem) &&
        selectedItem?.status === 'stored' &&
        selectedItem.cardGenerationStatus !== 'generating' &&
        !actionState,
      accent: 'cyan',
      onClick: () => selectedItem && onGenerateCard(selectedItem.collectionId),
    },
    {
      label:
        actionState?.kind === 'prepare_mint' && isSelectedActionRunning
          ? t('itemActions.preparingMint')
          : t('itemActions.prepareMint'),
      enabled:
        Boolean(selectedItem?.hasGeneratedCard) &&
        selectedItem?.status !== 'minted' &&
        selectedItem?.status !== 'shipped' &&
        !actionState,
      accent: 'yellow',
      onClick: () => selectedItem && onPrepareMint(selectedItem.collectionId),
    },
    {
      label:
        actionState?.kind === 'mint_nft' && isSelectedActionRunning
          ? t('itemActions.mintingOnChain')
          : t('itemActions.mintNft'),
      enabled:
        Boolean(selectedItem?.hasMintPrep) &&
        Boolean(selectedItem?.tokenUri) &&
        selectedItem?.status !== 'minted' &&
        selectedItem?.status !== 'shipped' &&
        !actionState,
      accent: 'green',
      onClick: () => onMintNFT?.(),
    },
    {
      label: t('itemActions.viewTokenUri'),
      enabled: Boolean(selectedItem?.tokenUri) && !actionState,
      accent: 'purple',
      onClick: () => onViewTokenUri(selectedItem?.tokenUri),
    },
  ] as const;

  const readiness = [
    { label: t('itemActions.cardGenerated'), active: Boolean(selectedItem?.hasGeneratedCard) },
    { label: t('itemActions.mintPrepared'), active: Boolean(selectedItem?.hasMintPrep) },
    { label: t('itemActions.nftLinked'), active: Boolean(selectedItem?.nftId) },
    { label: t('itemActions.minted'), active: selectedItem?.status === 'minted' || selectedItem?.status === 'shipped' },
  ];

  return (
    <InventorySectionFrame
      title={t('itemActions.title')}
      rightAdornment={
        <div className="rounded-full border border-cyan-300/15 bg-cyan-300/8 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.22em] text-cyan-100/80">
          {dataSource.toUpperCase()}
        </div>
      }
      contentClassName="space-y-5"
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.8fr)]">
        <div className="rounded-[1.35rem] border border-cyan-400/15 bg-[#071523]/75 p-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
            {t('itemActions.selectedUnit')}
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xl font-medium text-white">{selectedItem?.name ?? '—'}</p>
              <p className="mt-1 text-base text-slate-300/70">
                {selectedItem?.displayCode ?? '—'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedItem ? (
                <>
                  <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-cyan-100">
                    {selectedItem.statusLabel}
                  </span>
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-slate-200">
                    {selectedItem.cardStatusLabel}
                  </span>
                </>
              ) : null}
            </div>
          </div>
        </div>

        <div className="rounded-[1.35rem] border border-white/8 bg-white/5 p-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
            {t('itemActions.readinessMatrix')}
          </p>
          <div className="mt-4 space-y-3">
            {readiness.map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-3">
                <span className={item.active ? 'text-base text-white' : 'text-base text-slate-400'}>
                  {item.label}
                </span>
                <span
                  className={[
                    'rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em]',
                    item.active
                      ? 'border-emerald-300/25 bg-emerald-300/8 text-emerald-100'
                      : 'border-white/10 bg-white/5 text-slate-400',
                  ].join(' ')}
                >
                  {item.active ? t('itemActions.ready') : t('itemActions.pending')}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 rounded-[1.5rem] border border-white/6 bg-[#07101a]/80 p-4 backdrop-blur-lg">
        {actionItems.map((action) => {
          const accentClass =
            action.accent === 'yellow'
              ? 'border-yellow-300/25 bg-yellow-300/8 text-yellow-100'
              : action.accent === 'purple'
                ? 'border-fuchsia-300/20 bg-fuchsia-300/8 text-fuchsia-100'
                : action.accent === 'green'
                  ? 'border-emerald-300/25 bg-emerald-300/8 text-emerald-100'
                  : 'border-cyan-300/20 bg-cyan-300/8 text-cyan-100';

          return (
            <button
              key={action.label}
              type="button"
              disabled={!action.enabled}
              onClick={action.onClick}
              className={[
                'rounded-xl border px-4 py-3 text-base font-medium transition duration-200',
                'shadow-[0_0_16px_rgba(34,211,238,0.06)]',
                action.enabled
                  ? `${accentClass} hover:-translate-y-0.5 hover:shadow-[0_0_18px_rgba(34,211,238,0.18)]`
                  : 'cursor-not-allowed border-white/8 bg-white/5 text-slate-500',
              ].join(' ')}
            >
              {action.label}
            </button>
          );
        })}
      </div>

      {notice ? (
        <div
          className={[
            'rounded-2xl border px-4 py-3 text-base',
            notice.tone === 'success'
              ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100'
              : notice.tone === 'error'
                ? 'border-rose-300/20 bg-rose-300/8 text-rose-100'
                : 'border-cyan-300/20 bg-cyan-300/8 text-cyan-100',
          ].join(' ')}
        >
          {notice.message}
        </div>
      ) : null}
    </InventorySectionFrame>
  );
}
