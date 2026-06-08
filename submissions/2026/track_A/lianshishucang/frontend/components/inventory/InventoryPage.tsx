'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Menu } from 'lucide-react';
import InventoryHeader from './InventoryHeader';
import InventoryToolbar from './InventoryToolbar';
import InventoryGrid from './InventoryGrid';
import InventoryDetailPanel from './InventoryDetailPanel';
import InventoryStatsSummary from './InventoryStatsSummary';
import InventoryTradingMarketPanel from './InventoryTradingMarketPanel';
import InventorySideRail from './InventorySideRail';
import InventorySideRailDrawer from './InventorySideRailDrawer';
import InventoryBottomNav from './InventoryBottomNav';
import InventoryUploadPanel from './InventoryUploadPanel';
import InventoryMintPrepPanel from './InventoryMintPrepPanel';
import InventoryCollectionEditor from './InventoryCollectionEditor';
import InventoryWalletPanel from './InventoryWalletPanel';
import { filterAndSortInventoryItems, getPrimarySelection } from '../../lib/inventory/selectors';
import { useInventoryData } from '../../lib/inventory/useInventoryData';
import { useInventoryMarketData } from '../../lib/inventory/useInventoryMarketData';
import { useWallet } from '../../lib/web3/useWallet';
import { useContractWrite } from '../../lib/web3/useContractWrite';
import type {
  InventoryActionKind,
  InventoryCardFilterStatus,
  InventoryFilterStatus,
  InventorySortBy,
} from '../../types/inventory';
import InventorySectionFrame from './InventorySectionFrame';

export default function InventoryPage() {
  const {
    data,
    loading,
    error,
    token,
    dataSource,
    notice,
    actionState,
    conversionState,
    guidedStage,
    guidedCollectionId,
    setGuidedStage,
    setToken,
    clearToken,
    refresh,
    generateCardForItem,
    prepareMintForItem,
    viewTokenUriForItem,
    uploadCollection,
    oneClickConvert,
    saveCollectionMetadata,
  } = useInventoryData();

  const [activeWorkspace, setActiveWorkspace] = useState<'wallet' | 'business'>('business');
  const [activeBusinessSection, setActiveBusinessSection] = useState<'library' | 'upload' | 'prep' | 'market'>('library');
  const [activeWalletSection, setActiveWalletSection] = useState<'access'>('access');
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tokenInput, setTokenInput] = useState(token);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<InventoryFilterStatus>('all');
  const [cardFilter, setCardFilter] = useState<InventoryCardFilterStatus>('all');
  const [sortBy, setSortBy] = useState<InventorySortBy>('updated_desc');
  const [selectedId, setSelectedId] = useState<string | undefined>(data.items[0]?.id);

  useEffect(() => {
    setTokenInput(token);
  }, [token]);

  const visibleItems = useMemo(
    () =>
      filterAndSortInventoryItems(data.items, {
        searchQuery,
        statusFilter,
        cardFilter,
        sortBy,
      }),
    [cardFilter, data.items, searchQuery, sortBy, statusFilter],
  );

  const selectedItem = useMemo(() => {
    if (guidedCollectionId) {
      const guidedItem = visibleItems.find((item) => item.collectionId === guidedCollectionId);
      if (guidedItem) {
        return guidedItem;
      }
    }

    return getPrimarySelection(visibleItems, selectedId);
  }, [guidedCollectionId, selectedId, visibleItems]);

  const market = useInventoryMarketData(token, selectedItem);
  const wallet = useWallet();
  const contractWrite = useContractWrite();
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language?.startsWith('zh') ? 'zh' : 'en';
  const toggleLang = useCallback(() => {
    const next = currentLang === 'zh' ? 'en' : 'zh';
    i18n.changeLanguage(next);
    localStorage.setItem('i18nextLng', next);
  }, [currentLang, i18n]);
  const [mintNotice, setMintNotice] = useState<{ tone: 'info' | 'success' | 'error'; message: string } | null>(null);

  const handleMintNFT = useCallback(async () => {
    if (!selectedItem?.tokenUri) {
      return;
    }
    if (!wallet.address) {
      setMintNotice({ tone: 'error', message: t('mint.connectWallet') });
      return;
    }
    setMintNotice({ tone: 'info', message: t('mint.mintingOnChain') });
    try {
      const hash = await contractWrite.mintNFT(
        wallet.address,
        selectedItem.tokenUri,
        selectedItem.royaltyFee ?? 250,
      );
      setMintNotice({ tone: 'success', message: t('mint.mintedTx', { hash: hash.slice(0, 10) }) });
      setGuidedStage('mint');
      await refresh();
    } catch (err: unknown) {
      setMintNotice({
        tone: 'error',
        message: err instanceof Error ? err.message : t('mint.mintFailed'),
      });
    }
  }, [selectedItem, wallet.address, contractWrite, refresh]);

  useEffect(() => {
    if (!visibleItems.length) {
      setSelectedId(undefined);
      return;
    }

    if (guidedCollectionId) {
      const guidedItem = visibleItems.find((item) => item.collectionId === guidedCollectionId);
      if (guidedItem) {
        setSelectedId(guidedItem.id);
        return;
      }
    }

    if (!selectedId || !visibleItems.some((item) => item.id === selectedId)) {
      setSelectedId(visibleItems[0]?.id);
    }
  }, [guidedCollectionId, selectedId, visibleItems]);

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#121528] pb-28 text-white xl:pb-10">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_16%_18%,rgba(255,255,255,0.9),transparent_14%),radial-gradient(circle_at_34%_38%,rgba(125,211,252,0.72),transparent_18%),radial-gradient(circle_at_58%_18%,rgba(253,224,71,0.46),transparent_18%),radial-gradient(circle_at_84%_22%,rgba(244,114,182,0.62),transparent_20%),radial-gradient(circle_at_82%_74%,rgba(216,180,254,0.7),transparent_22%),radial-gradient(circle_at_18%_80%,rgba(103,232,249,0.52),transparent_20%),linear-gradient(135deg,rgba(248,239,255,0.98),rgba(234,253,255,0.96)_20%,rgba(251,244,205,0.88)_42%,rgba(252,214,236,0.92)_68%,rgba(228,217,255,0.96))]" />
      <div className="pointer-events-none fixed inset-0 opacity-60 [background-image:radial-gradient(circle_at_18%_32%,rgba(255,255,255,0.34)_0,transparent_12%),radial-gradient(circle_at_72%_18%,rgba(255,255,255,0.26)_0,transparent_14%),radial-gradient(circle_at_64%_74%,rgba(226,232,240,0.18)_0,transparent_18%),repeating-linear-gradient(112deg,rgba(255,255,255,0.1)_0,rgba(255,255,255,0.1)_2px,transparent_2px,transparent_20px),repeating-linear-gradient(24deg,rgba(255,255,255,0.06)_0,rgba(255,255,255,0.06)_1px,transparent_1px,transparent_14px),linear-gradient(110deg,transparent_0%,rgba(255,255,255,0.16)_32%,transparent_42%,rgba(255,255,255,0.12)_54%,transparent_66%,rgba(255,255,255,0.1)_78%,transparent_100%)]" />
      <div className="pointer-events-none fixed inset-0 opacity-40 blur-[68px] bg-[radial-gradient(circle_at_24%_28%,rgba(255,255,255,0.42),transparent_26%),radial-gradient(circle_at_70%_24%,rgba(244,114,182,0.26),transparent_26%),radial-gradient(circle_at_52%_66%,rgba(34,211,238,0.24),transparent_28%),radial-gradient(circle_at_82%_70%,rgba(196,181,253,0.24),transparent_26%)]" />
      <div className="pointer-events-none fixed inset-0 opacity-22 bg-[linear-gradient(125deg,transparent_0%,rgba(255,255,255,0.24)_26%,transparent_34%,rgba(255,255,255,0.14)_48%,transparent_58%,rgba(255,255,255,0.18)_74%,transparent_100%)] mix-blend-screen" />
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(180deg,rgba(8,14,32,0.3),rgba(9,18,38,0.42)_34%,rgba(8,16,34,0.62)_68%,rgba(7,13,28,0.78)_100%)]" />
      <div className="pointer-events-none fixed inset-0 opacity-[0.06] [background-image:linear-gradient(rgba(8,145,178,0.36)_1px,transparent_1px),linear-gradient(90deg,rgba(8,145,178,0.36)_1px,transparent_1px)] [background-size:132px_132px] [mask-image:linear-gradient(180deg,white,transparent)]" />

      <InventorySideRailDrawer
        open={drawerOpen}
        workspace={activeWorkspace}
        activeSection={activeWorkspace === 'business' ? activeBusinessSection : activeWalletSection}
        onChange={(section) => {
          if (activeWorkspace === 'business' && section !== 'access') {
            setActiveBusinessSection(section);
          }
          if (activeWorkspace === 'wallet' && section === 'access') {
            setActiveWalletSection('access');
          }
        }}
        onClose={() => setDrawerOpen(false)}
      />

      <div className="relative z-20 mx-auto flex w-full max-w-[1700px] gap-6 px-4 py-6 sm:px-6 lg:px-8 xl:px-10">
        <div className="min-w-0 flex-1 space-y-6">
          <div className="flex items-center justify-between">
            <div className="rounded-full border border-cyan-300/15 bg-cyan-300/8 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.22em] text-cyan-100/80">
              {activeWorkspace === 'business' ? activeBusinessSection : activeWalletSection}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={toggleLang}
                className="rounded-full border border-fuchsia-300/15 bg-fuchsia-300/8 px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-fuchsia-100 transition hover:border-fuchsia-300/30"
              >
                {currentLang === 'zh' ? 'EN' : '中文'}
              </button>
              <button
                type="button"
                onClick={() => setDrawerOpen(true)}
                className="rounded-full border border-white/10 bg-[#06111c]/85 p-3 text-slate-300 transition hover:border-cyan-300/20 hover:text-white xl:hidden"
              >
                <Menu size={18} />
              </button>
            </div>
          </div>

          {activeWorkspace === 'wallet' && activeWalletSection === 'access' ? (
            <InventorySectionFrame title={t('access.title')} rightAdornment={
              <button
                type="button"
                onClick={clearToken}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 transition hover:border-cyan-300/30 hover:text-white"
              >
                {t('access.clear')}
              </button>
            } contentClassName="space-y-4">
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.8fr)_auto_auto] lg:items-end">
                <label className="block">
                  <span className="mb-2 block font-mono text-[12px] uppercase tracking-[0.26em] text-cyan-300/70 sm:text-[13px]">
                    {t('access.jwt')}
                  </span>
                  <textarea
                    value={tokenInput}
                    onChange={(event) => setTokenInput(event.target.value)}
                    placeholder={t('access.jwtPlaceholder')}
                    rows={3}
                    className="w-full rounded-2xl border border-cyan-400/15 bg-[#071523]/80 px-4 py-3 text-base text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/45 focus:shadow-[0_0_0_1px_rgba(103,232,249,0.2)]"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => setToken(tokenInput)}
                  className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 px-5 py-3 text-base font-medium text-cyan-100 transition hover:-translate-y-0.5 hover:shadow-[0_0_18px_rgba(34,211,238,0.18)]"
                >
                  {t('access.saveLoad')}
                </button>
                <button
                  type="button"
                  onClick={() => void refresh()}
                  className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-base font-medium text-slate-200 transition hover:border-cyan-300/20 hover:text-white"
                >
                  {t('access.sync')}
                </button>
              </div>

              <div className="flex flex-wrap gap-3 text-base text-slate-300/75">
                <span className="rounded-full border border-cyan-300/15 bg-cyan-300/8 px-3 py-1">
                  {t('access.mode', { mode: dataSource.toUpperCase() })}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
                  {t('access.token', { status: token ? t('access.loaded') : t('access.demoOnly') })}
                </span>
                {loading ? (
                  <span className="rounded-full border border-yellow-300/15 bg-yellow-300/8 px-3 py-1 text-yellow-100">
                    {t('access.syncing')}
                  </span>
                ) : null}
              </div>

              {error ? (
                <div className="rounded-2xl border border-rose-300/20 bg-rose-300/8 px-4 py-3 text-base text-rose-100">
                  {error}
                </div>
              ) : null}

              <InventoryWalletPanel wallet={wallet} />
            </InventorySectionFrame>
          ) : null}

          {activeWorkspace === 'business' && activeBusinessSection === 'library' ? (
            <div className="space-y-6">
              <InventoryHeader selectedItem={selectedItem} dataSource={dataSource} />
              <InventoryStatsSummary stats={data.stats} />

              <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(360px,0.9fr)]">
                <div className="space-y-6">
                  <InventoryToolbar
                    searchQuery={searchQuery}
                    statusFilter={statusFilter}
                    cardFilter={cardFilter}
                    sortBy={sortBy}
                    resultCount={visibleItems.length}
                    onSearchQueryChange={setSearchQuery}
                    onStatusFilterChange={setStatusFilter}
                    onCardFilterChange={setCardFilter}
                    onSortByChange={setSortBy}
                  />
                  <InventoryGrid
                    items={visibleItems}
                    selectedId={selectedItem?.id}
                    onSelect={setSelectedId}
                  />
                </div>

                <div className="space-y-6">
                  <InventoryDetailPanel item={selectedItem} />
                </div>
              </div>
            </div>
          ) : null}

          {activeWorkspace === 'business' && activeBusinessSection === 'upload' ? (
            <div className="space-y-6">
              <InventoryUploadPanel
                token={token}
                selectedItem={selectedItem}
                conversionState={conversionState}
                notice={notice}
                onUpload={uploadCollection}
                onOneClickConvert={oneClickConvert}
                guidedStage={guidedStage}
                onGuidedStageChange={setGuidedStage}
              />

              {guidedStage === 'review' ? (
                <InventoryCollectionEditor
                  selectedItem={selectedItem}
                  notice={notice}
                  onSubmit={(payload) =>
                    selectedItem ? saveCollectionMetadata(selectedItem.collectionId, payload) : Promise.resolve()
                  }
                  onBack={() => setGuidedStage('upload')}
                  onContinue={() => setGuidedStage('card')}
                  submitting={actionState?.kind === 'refresh'}
                />
              ) : null}

              {guidedStage === 'card' ? (
                <InventoryMintPrepPanel
                  selectedItem={selectedItem}
                  onRefresh={() => void refresh()}
                  onGenerateCard={(collectionId) => void generateCardForItem(collectionId)}
                  onPrepareMint={(collectionId) => void prepareMintForItem(collectionId)}
                  onViewTokenUri={(tokenUri) => void viewTokenUriForItem(tokenUri)}
                  onMintNFT={handleMintNFT}
                  actionState={actionState}
                  notice={notice}
                  dataSource={dataSource}
                  wallet={wallet}
                />
              ) : null}

              {guidedStage === 'mint' ? (
                <>
                  <InventorySectionFrame title={t('mint.mintStage')} contentClassName="space-y-4">
                    <div className="rounded-[1.35rem] border border-cyan-400/12 bg-[#08131f]/75 p-4">
                      <p className="font-mono text-[12px] uppercase tracking-[0.24em] text-cyan-300/65 sm:text-[13px]">{t('mint.tokenUri')}</p>
                      <p className="mt-3 break-all text-lg font-medium text-white">{conversionState.tokenUri ?? '—'}</p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => conversionState.tokenUri && void viewTokenUriForItem(conversionState.tokenUri)}
                        className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 px-4 py-3 text-base font-medium text-cyan-100 transition hover:-translate-y-0.5"
                      >
                        {t('mint.viewTokenUri')}
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveBusinessSection('prep')}
                        className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-base font-medium text-slate-200 transition hover:border-cyan-300/20 hover:text-white"
                      >
                        {t('mint.openNftPrep')}
                      </button>
                    </div>
                    {mintNotice ? (
                      <div className={[
                        'rounded-2xl border px-4 py-3 text-base',
                        mintNotice.tone === 'success'
                          ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100'
                          : mintNotice.tone === 'error'
                            ? 'border-rose-300/20 bg-rose-300/8 text-rose-100'
                            : 'border-cyan-300/20 bg-cyan-300/8 text-cyan-100',
                      ].join(' ')}>
                        {mintNotice.message}
                      </div>
                    ) : null}
                  </InventorySectionFrame>
                  <InventoryMintPrepPanel
                    selectedItem={selectedItem}
                    onRefresh={() => void refresh()}
                    onGenerateCard={(collectionId) => void generateCardForItem(collectionId)}
                    onPrepareMint={(collectionId) => void prepareMintForItem(collectionId)}
                    onViewTokenUri={(tokenUri) => void viewTokenUriForItem(tokenUri)}
                    onMintNFT={handleMintNFT}
                    actionState={actionState}
                    notice={notice}
                    dataSource={dataSource}
                    wallet={wallet}
                  />
                </>
              ) : null}
            </div>
          ) : null}

          {activeWorkspace === 'business' && activeBusinessSection === 'prep' ? (
            <InventoryMintPrepPanel
              selectedItem={selectedItem}
              onRefresh={() => void refresh()}
              onGenerateCard={(collectionId) => void generateCardForItem(collectionId)}
              onPrepareMint={(collectionId) => void prepareMintForItem(collectionId)}
              onViewTokenUri={(tokenUri) => void viewTokenUriForItem(tokenUri)}
              onMintNFT={handleMintNFT}
              actionState={actionState}
              notice={notice}
              dataSource={dataSource}
              wallet={wallet}
            />
          ) : null}

          {activeWorkspace === 'business' && activeBusinessSection === 'market' ? (
            <InventoryTradingMarketPanel
              market={market.market}
              loading={market.loading}
              error={market.error}
              selectedItem={selectedItem}
            />
          ) : null}

        </div>

        <InventorySideRail
          workspace={activeWorkspace}
          activeSection={activeWorkspace === 'business' ? activeBusinessSection : activeWalletSection}
          onChange={(section) => {
            if (activeWorkspace === 'business' && section !== 'access') {
              setActiveBusinessSection(section);
            }
            if (activeWorkspace === 'wallet' && section === 'access') {
              setActiveWalletSection('access');
            }
          }}
          collapsed={railCollapsed}
          onToggle={() => setRailCollapsed((value) => !value)}
        />
      </div>

      <InventoryBottomNav activeTab={activeWorkspace} onChange={setActiveWorkspace} />
    </div>
  );
}
