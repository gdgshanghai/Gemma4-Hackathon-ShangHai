import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useWallet } from '../../lib/web3/useWallet';
import { useContractWrite } from '../../lib/web3/useContractWrite';
import { NFT_CONTRACT_ADDRESS, MARKETPLACE_CONTRACT_ADDRESS } from '../../lib/web3/config';
import InventoryDetailPanel from './InventoryDetailPanel';
import InventoryEmptyState from './InventoryEmptyState';
import InventorySectionFrame from './InventorySectionFrame';
import type {
  InventoryItemViewModel,
  InventoryMarketData,
  InventoryMarketListingViewModel,
  InventoryMarketOfferViewModel,
} from '../../types/inventory';

interface InventoryTradingMarketPanelProps {
  market: InventoryMarketData;
  loading: boolean;
  error: string | null;
  selectedItem?: InventoryItemViewModel;
}

export default function InventoryTradingMarketPanel({
  market,
  loading,
  error,
  selectedItem,
}: InventoryTradingMarketPanelProps) {
  const wallet = useWallet();
  const contract = useContractWrite();
  const { t } = useTranslation();
  const [actionState, setActionState] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{ tone: string; message: string } | null>(null);

  const [createListingOpen, setCreateListingOpen] = useState(false);
  const [listPriceEth, setListPriceEth] = useState('');

  const [updatePriceListingId, setUpdatePriceListingId] = useState<number | null>(null);
  const [updatePriceEth, setUpdatePriceEth] = useState('');

  const [offerListingId, setOfferListingId] = useState<number | null>(null);
  const [offerPriceEth, setOfferPriceEth] = useState('');
  const [offerExpirationHours, setOfferExpirationHours] = useState('48');

  const [offers, setOffers] = useState<InventoryMarketOfferViewModel[]>([]);
  const [offersLoading, setOffersLoading] = useState(false);

  const clearNotice = () => setActionNotice(null);

  const loadOffers = useCallback(async () => {
    if (!selectedItem?.nftId) {
      setOffers([]);
      return;
    }
    setOffersLoading(true);
    try {
      const rawOffers = await contract.getOffersForToken(selectedItem.nftId);
      const now = Math.floor(Date.now() / 1000);
      const mapped: InventoryMarketOfferViewModel[] = rawOffers
        .filter((o: any) => o.active)
        .map((o: any) => ({
          id: `offer-${o.offerId}`,
          offerId: o.offerId.toString(),
          tokenId: Number(o.tokenId),
          nftContract: o.nftContract,
          bidder: o.bidder,
          bidderLabel: wallet.formatAddress(o.bidder),
          priceWei: o.price.toString(),
          priceEthLabel: formatWei(o.price.toString()),
          expiration: Number(o.expiration),
          active: o.active,
          createdAt: Number(o.createdAt),
          isExpired: Number(o.expiration) < now,
        }));
      setOffers(mapped);
    } catch {
      setOffers([]);
    } finally {
      setOffersLoading(false);
    }
  }, [selectedItem?.nftId, contract, wallet]);

  useEffect(() => {
    if (selectedItem?.nftId) {
      void loadOffers();
    } else {
      setOffers([]);
    }
  }, [selectedItem?.nftId, loadOffers]);

  const requireWallet = () => {
    if (!wallet.isConnected) {
      setActionNotice({ tone: 'error', message: t('marketPanel.notConnectedError') });
      return false;
    }
    if (!wallet.isCorrectChain) {
      setActionNotice({ tone: 'error', message: t('marketPanel.wrongNetworkError') });
      return false;
    }
    return true;
  };

  const handleBuy = async (listingId: number, priceWei: string) => {
    if (!requireWallet()) return;
    setActionState(`buy-${listingId}`);
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmPurchase') });
    try {
      const hash = await contract.buyItem(listingId, priceWei);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.purchased', { hash: hash.slice(0, 10) }) });
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.purchaseFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleCancelListing = async (listingId: number) => {
    if (!requireWallet()) return;
    setActionState(`cancel-${listingId}`);
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmCancellation') });
    try {
      const hash = await contract.cancelListing(listingId);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.listingCancelled', { hash: hash.slice(0, 10) }) });
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.cancelFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleCreateListing = async () => {
    if (!requireWallet()) return;
    if (!selectedItem?.nftId || !listPriceEth) return;
    const priceWei = BigInt(Math.floor(parseFloat(listPriceEth) * 1e18)).toString();
    setActionState('create-listing');
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmListing') });
    try {
      const hash = await contract.createListing(NFT_CONTRACT_ADDRESS, selectedItem.nftId, priceWei);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.listed', { hash: hash.slice(0, 10) }) });
      setCreateListingOpen(false);
      setListPriceEth('');
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.listingFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleApprove = async () => {
    if (!requireWallet() || !selectedItem?.nftId) return;
    setActionState('approve');
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmApproval') });
    try {
      const hash = await contract.approveNFT(NFT_CONTRACT_ADDRESS, MARKETPLACE_CONTRACT_ADDRESS, selectedItem.nftId);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.approved', { hash: hash.slice(0, 10) }) });
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.approvalFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleUpdatePrice = async (listingId: number) => {
    if (!requireWallet() || !updatePriceEth) return;
    const newPriceWei = BigInt(Math.floor(parseFloat(updatePriceEth) * 1e18)).toString();
    setActionState(`update-price-${listingId}`);
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmPriceUpdate') });
    try {
      const hash = await contract.updatePrice(listingId, newPriceWei);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.priceUpdated', { hash: hash.slice(0, 10) }) });
      setUpdatePriceListingId(null);
      setUpdatePriceEth('');
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.updatePriceFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleCreateOffer = async (nftContract: string, tokenId: number) => {
    if (!requireWallet() || !offerPriceEth) return;
    const priceWei = BigInt(Math.floor(parseFloat(offerPriceEth) * 1e18)).toString();
    const hours = parseInt(offerExpirationHours) || 48;
    const expiration = Math.floor(Date.now() / 1000) + hours * 3600;
    setActionState(`create-offer-${tokenId}`);
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmOffer') });
    try {
      const hash = await contract.createOffer(nftContract, tokenId, priceWei, expiration);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.offerCreated', { hash: hash.slice(0, 10) }) });
      setOfferListingId(null);
      setOfferPriceEth('');
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.createOfferFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleCancelOffer = async (tokenId: number, offerIndex: number) => {
    if (!requireWallet()) return;
    setActionState(`cancel-offer-${offerIndex}`);
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmCancelOffer') });
    try {
      const hash = await contract.cancelOffer(tokenId, offerIndex);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.offerCancelled', { hash: hash.slice(0, 10) }) });
      void loadOffers();
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.cancelOfferFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleAcceptOffer = async (nftContract: string, tokenId: number, offerIndex: number) => {
    if (!requireWallet()) return;
    setActionState(`accept-offer-${offerIndex}`);
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmAcceptOffer') });
    try {
      const hash = await contract.acceptOffer(nftContract, tokenId, offerIndex);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.offerAccepted', { hash: hash.slice(0, 10) }) });
      void loadOffers();
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.acceptOfferFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const handleSetApprovalForAll = async () => {
    if (!requireWallet()) return;
    setActionState('approve-all');
    setActionNotice({ tone: 'info' as const, message: t('marketPanel.confirmApproval') });
    try {
      const hash = await contract.setApprovalForAll(NFT_CONTRACT_ADDRESS, MARKETPLACE_CONTRACT_ADDRESS, true);
      setActionNotice({ tone: 'success' as const, message: t('marketPanel.approvedAll', { hash: hash.slice(0, 10) }) });
    } catch (err: unknown) {
      setActionNotice({
        tone: 'error' as const,
        message: err instanceof Error ? err.message : t('marketPanel.approvalFailed'),
      });
    } finally {
      setActionState(null);
    }
  };

  const selectedPresence = [
    {
      label: t('marketPanel.nftLinked'),
      value: market.selectedNft ? market.selectedNft.tokenId : t('common.pending'),
      active: Boolean(market.selectedNft),
    },
    {
      label: t('marketPanel.listed'),
      value: market.summary.selectedItemListed ? t('common.live') : t('common.no'),
      active: market.summary.selectedItemListed,
    },
    {
      label: t('marketPanel.owner'),
      value: market.selectedNft?.ownerLabel ?? t('common.unavailable'),
      active: Boolean(market.selectedNft?.ownerLabel),
    },
  ];

  const canList =
    Boolean(selectedItem?.nftId) &&
    wallet.isConnected &&
    wallet.isCorrectChain &&
    !market.summary.selectedItemListed;

  return (
    <div className="space-y-6">
      {actionNotice ? (
        <div
          onClick={clearNotice}
          className={[
            'cursor-pointer rounded-2xl border px-4 py-3 text-base',
            actionNotice.tone === 'success'
              ? 'border-emerald-300/20 bg-emerald-300/8 text-emerald-100'
              : actionNotice.tone === 'error'
                ? 'border-rose-300/20 bg-rose-300/8 text-rose-100'
                : 'border-cyan-300/20 bg-cyan-300/8 text-cyan-100',
          ].join(' ')}
        >
          {actionNotice.message}
        </div>
      ) : null}

      <InventorySectionFrame title={t('marketPanel.marketVisibility')} contentClassName="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard label={t('marketPanel.activeListings')} value={market.summary.activeListings} />
          <SummaryCard label={t('marketPanel.myOwnedNfts')} value={market.summary.ownedNfts} />
          <SummaryCard label={t('marketPanel.myCreatedNfts')} value={market.summary.createdNfts} />
        </div>

        {!wallet.isConnected ? (
          <div className="rounded-2xl border border-yellow-300/20 bg-yellow-300/8 px-4 py-3 text-base text-yellow-100">
            {t('marketPanel.connectWalletNotice')}
          </div>
        ) : !wallet.isCorrectChain ? (
          <div className="rounded-2xl border border-yellow-300/20 bg-yellow-300/8 px-4 py-3 text-base text-yellow-100">
            {t('marketPanel.wrongNetworkNotice')}
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-2xl border border-yellow-300/20 bg-yellow-300/8 px-4 py-3 text-base text-yellow-100">
            {t('common.loading')}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-2xl border border-rose-300/20 bg-rose-300/8 px-4 py-3 text-base text-rose-100">
            {error}
          </div>
        ) : null}
      </InventorySectionFrame>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(360px,1.05fr)]">
        <div className="space-y-6">
          <InventorySectionFrame title={t('marketPanel.selectedItemPresence')} contentClassName="space-y-4">
            <div className="rounded-[1.35rem] border border-cyan-400/15 bg-[#071523]/75 p-4">
              <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
                {t('marketPanel.tradingFocus')}
              </p>
              <p className="mt-3 text-xl font-medium text-white">
                {selectedItem?.name ?? t('common.none')}
              </p>
              <p className="mt-1 text-base text-slate-300/70">
                {selectedItem?.displayCode ?? t('common.none')}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {selectedPresence.map((entry) => (
                <div key={entry.label} className="rounded-[1.2rem] border border-white/8 bg-white/5 p-4">
                  <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan-300/60">
                    {entry.label}
                  </p>
                  <p className="mt-3 break-all text-base font-medium text-white">{entry.value}</p>
                  <span
                    className={[
                      'mt-3 inline-flex rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em]',
                      entry.active
                        ? 'border-emerald-300/25 bg-emerald-300/8 text-emerald-100'
                        : 'border-white/10 bg-white/5 text-slate-400',
                    ].join(' ')}
                  >
                    {entry.active ? t('common.live') : t('common.pending')}
                  </span>
                </div>
              ))}
            </div>

            {selectedItem?.nftId ? (
              <div className="flex flex-wrap gap-3 rounded-[1.5rem] border border-white/6 bg-[#07101a]/80 p-4 backdrop-blur-lg">
                <button
                  type="button"
                  disabled={actionState === 'approve'}
                  onClick={handleApprove}
                  className="rounded-xl border border-cyan-300/20 bg-cyan-300/8 px-4 py-3 text-base font-medium text-cyan-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:border-white/8 disabled:bg-white/5 disabled:text-slate-500"
                >
                  {actionState === 'approve' ? t('marketPanel.approving') : t('marketPanel.approveNft')}
                </button>
                <button
                  type="button"
                  disabled={actionState === 'approve-all'}
                  onClick={handleSetApprovalForAll}
                  className="rounded-xl border border-cyan-300/20 bg-cyan-300/8 px-4 py-3 text-base font-medium text-cyan-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:border-white/8 disabled:bg-white/5 disabled:text-slate-500"
                >
                  {actionState === 'approve-all' ? t('marketPanel.approving') : t('marketPanel.approveAll')}
                </button>
                <button
                  type="button"
                  disabled={!canList || actionState === 'create-listing'}
                  onClick={() => setCreateListingOpen(true)}
                  className="rounded-xl border border-yellow-300/20 bg-yellow-300/8 px-4 py-3 text-base font-medium text-yellow-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:border-white/8 disabled:bg-white/5 disabled:text-slate-500"
                >
                  {actionState === 'create-listing' ? t('marketPanel.listing') : t('marketPanel.createListing')}
                </button>

                {createListingOpen ? (
                  <div className="flex w-full flex-wrap items-end gap-3">
                    <label className="min-w-0 flex-1">
                      <span className="mb-1 block font-mono text-[11px] uppercase tracking-[0.24em] text-cyan-300/60">
                        {t('marketPanel.priceEth')}
                      </span>
                      <input
                        type="number"
                        step="0.001"
                        min="0"
                        value={listPriceEth}
                        onChange={(e) => setListPriceEth(e.target.value)}
                        placeholder={t('marketPanel.pricePlaceholder')}
                        className="w-full rounded-xl border border-cyan-400/15 bg-[#071523]/80 px-4 py-3 text-base text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/45"
                      />
                    </label>
                    <button
                      type="button"
                      disabled={!listPriceEth || parseFloat(listPriceEth) <= 0}
                      onClick={handleCreateListing}
                      className="rounded-xl border border-emerald-300/20 bg-emerald-300/8 px-5 py-3 text-base font-medium text-emerald-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:border-white/8 disabled:bg-white/5 disabled:text-slate-500"
                    >
                      {t('marketPanel.confirm')}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setCreateListingOpen(false); setListPriceEth(''); }}
                      className="rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-base font-medium text-slate-200 transition hover:border-rose-300/20 hover:bg-rose-300/8 hover:text-rose-100"
                    >
                      {t('marketPanel.cancel')}
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}

            {selectedItem?.nftId ? (
              <InventorySectionFrame title={t('marketPanel.offersTitle')} contentClassName="space-y-4">
                {offersLoading ? (
                  <div className="rounded-2xl border border-yellow-300/20 bg-yellow-300/8 px-4 py-3 text-base text-yellow-100">
                    {t('marketPanel.loadingOffers')}
                  </div>
                ) : offers.length > 0 ? (
                  <div className="grid gap-3">
                    {offers.map((offer, idx) => {
                      const isOwnOffer = wallet.isConnected && offer.bidder.toLowerCase() === wallet.address.toLowerCase();
                      const isOwner = wallet.isConnected && market.selectedNft?.ownerLabel && market.selectedNft.ownerLabel.toLowerCase().includes(wallet.address.toLowerCase().slice(2, 8));
                      return (
                        <div key={offer.id} className="rounded-[1.35rem] border border-white/8 bg-white/5 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-base font-medium text-white">
                                {offer.priceEthLabel} — by {offer.bidderLabel}
                              </p>
                              <p className="mt-1 text-sm text-slate-300/70">
                                  {offer.isExpired ? t('common.expired') : new Date(offer.expiration * 1000).toLocaleString()}
                              </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {offer.isExpired ? (
                                <span className="rounded-full border border-rose-300/20 bg-rose-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-rose-100">
                                  {t('common.expired')}
                                </span>
                              ) : (
                                <span className="rounded-full border border-emerald-300/20 bg-emerald-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-emerald-100">
                                  {t('common.active')}
                                </span>
                              )}
                              {isOwnOffer ? (
                                <button
                                  type="button"
                                  disabled={actionState === `cancel-offer-${idx}`}
                                  onClick={() => handleCancelOffer(offer.tokenId, idx)}
                                  className="rounded-xl border border-rose-300/15 bg-rose-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-rose-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  {actionState === `cancel-offer-${idx}` ? t('marketPanel.cancellingOffer') : t('marketPanel.cancel')}
                                </button>
                ) : null}
              </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-[1.35rem] border border-white/8 bg-white/5 p-4">
                    <p className="text-base text-slate-300/70">{t('marketPanel.noOffers')}</p>
                  </div>
                )}
              </InventorySectionFrame>
            ) : null}
          </InventorySectionFrame>

          <InventorySectionFrame title={t('marketPanel.activityTitle')} contentClassName="space-y-4">
            <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-5">
              <span className="inline-flex rounded-full border border-yellow-300/20 bg-yellow-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-yellow-100">
                {t('marketPanel.chainEventsSync')}
              </span>
            </div>
          </InventorySectionFrame>

          <div className="grid gap-6 xl:grid-cols-2">
            <MarketListSection
              title={t('marketPanel.marketplaceListings')}
              items={market.listings}
              emptyTitle={t('marketPanel.noActiveListings')}
              emptyMessage={t('marketPanel.noActiveListingsMsg')}
              renderItem={(item) => (
                <ListingCard
                  key={item.id}
                  item={item}
                  actionState={actionState}
                  wallet={wallet}
                  onBuy={() => handleBuy(Number(item.listingId), item.priceWei)}
                  onCancel={() => handleCancelListing(Number(item.listingId))}
                  onUpdatePriceOpen={() => {
                    setUpdatePriceListingId(Number(item.listingId));
                    setUpdatePriceEth('');
                  }}
                  onUpdatePriceConfirm={() => handleUpdatePrice(Number(item.listingId))}
                  updatePriceOpen={updatePriceListingId === Number(item.listingId)}
                  updatePriceEth={updatePriceEth}
                  onUpdatePriceEthChange={setUpdatePriceEth}
                  onOfferOpen={() => {
                    setOfferListingId(Number(item.listingId));
                    setOfferPriceEth('');
                  }}
                  onOfferConfirm={(nftContract, tokenId) => handleCreateOffer(nftContract, tokenId)}
                  offerOpen={offerListingId === Number(item.listingId)}
                  offerPriceEth={offerPriceEth}
                  onOfferPriceEthChange={setOfferPriceEth}
                  offerExpirationHours={offerExpirationHours}
                  onOfferExpirationHoursChange={setOfferExpirationHours}
                />
              )}
            />
          </div>
        </div>

        <div className="space-y-6">
          <InventoryDetailPanel item={selectedItem} />
        </div>
      </div>
    </div>
  );
}

interface SummaryCardProps {
  label: string;
  value: number;
}

function formatWei(wei: string): string {
  try {
    const value = BigInt(wei || '0');
    const whole = value / 1000000000000000000n;
    const fraction = value % 1000000000000000000n;
    const fractionString = fraction.toString().padStart(18, '0').slice(0, 4).replace(/0+$/, '');
    return fractionString ? `${whole}.${fractionString} ETH` : `${whole} ETH`;
  } catch {
    return '—';
  }
}

function SummaryCard({ label, value }: SummaryCardProps) {
  return (
    <div className="rounded-[1.35rem] border border-cyan-400/12 bg-[#08131f]/75 p-4 shadow-[0_0_18px_rgba(34,211,238,0.06)]">
      <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-cyan-300/65">{label}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
    </div>
  );
}

interface MarketListSectionProps<T> {
  title: string;
  items: T[];
  emptyTitle: string;
  emptyMessage: string;
  renderItem: (item: T) => React.ReactNode;
}

function MarketListSection<T>({
  title,
  items,
  emptyTitle,
  emptyMessage,
  renderItem,
}: MarketListSectionProps<T>) {
  return (
    <InventorySectionFrame title={title} contentClassName="space-y-4">
      {items.length ? (
        <div className="grid gap-4">{items.map((item) => renderItem(item))}</div>
      ) : (
        <InventoryEmptyState title={emptyTitle} message={emptyMessage} />
      )}
    </InventorySectionFrame>
  );
}

interface ListingCardProps {
  item: InventoryMarketListingViewModel;
  actionState: string | null;
  wallet: { isConnected: boolean; isCorrectChain: boolean; address: string };
  onBuy: () => void;
  onCancel: () => void;
  onUpdatePriceOpen?: () => void;
  onUpdatePriceConfirm?: (newPriceEth: string) => void;
  updatePriceOpen?: boolean;
  updatePriceEth?: string;
  onUpdatePriceEthChange?: (val: string) => void;
  onOfferOpen?: () => void;
  onOfferConfirm?: (nftContract: string, tokenId: number) => void;
  offerOpen?: boolean;
  offerPriceEth?: string;
  onOfferPriceEthChange?: (val: string) => void;
  offerExpirationHours?: string;
  onOfferExpirationHoursChange?: (val: string) => void;
}

function ListingCard({
  item,
  actionState,
  wallet,
  onBuy,
  onCancel,
  onUpdatePriceOpen,
  onUpdatePriceConfirm,
  updatePriceOpen,
  updatePriceEth,
  onUpdatePriceEthChange,
  onOfferOpen,
  onOfferConfirm,
  offerOpen,
  offerPriceEth,
  onOfferPriceEthChange,
  offerExpirationHours,
  onOfferExpirationHoursChange,
}: ListingCardProps) {
  const { t } = useTranslation();
  const isOwn = wallet.isConnected && item.sellerLabel.toLowerCase().includes(wallet.address.toLowerCase().slice(2, 8));
  return (
    <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
      <div className="flex gap-4">
        <img src={item.imageUrl} alt={item.title} className="h-24 w-24 rounded-2xl object-cover" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xl font-medium text-white">{item.title}</p>
              <p className="mt-1 text-base text-slate-300/70">{t('marketPanel.seller', { label: item.sellerLabel })}</p>
            </div>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-cyan-100">
              {item.status}
            </span>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-slate-200">
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">{item.priceEthLabel}</span>
            {item.isSelectedItemMatch ? (
              <span className="rounded-full border border-yellow-300/20 bg-yellow-300/8 px-3 py-1 text-yellow-100">
                {t('common.match')}
              </span>
            ) : null}
            {isOwn ? (
              <>
                <button
                  type="button"
                  disabled={actionState === `cancel-${item.listingId}`}
                  onClick={onCancel}
                  className="rounded-xl border border-rose-300/15 bg-rose-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-rose-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {actionState === `cancel-${item.listingId}` ? t('marketPanel.cancelling') : t('marketPanel.cancelListing')}
                </button>
                <button
                  type="button"
                  disabled={actionState === `update-price-${item.listingId}`}
                  onClick={onUpdatePriceOpen}
                  className="rounded-xl border border-yellow-300/15 bg-yellow-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-yellow-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {actionState === `update-price-${item.listingId}` ? t('marketPanel.updating') : t('marketPanel.updatePrice')}
                </button>
                {updatePriceOpen ? (
                  <div className="flex w-full flex-wrap items-end gap-2">
                    <label className="min-w-0 flex-1">
                      <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-300/60">
                        {t('marketPanel.newPriceEth')}
                      </span>
                      <input
                        type="number"
                        step="0.001"
                        min="0"
                        value={updatePriceEth}
                        onChange={(e) => onUpdatePriceEthChange?.(e.target.value)}
                        placeholder={t('marketPanel.pricePlaceholder')}
                        className="w-full rounded-xl border border-cyan-400/15 bg-[#071523]/80 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/45"
                      />
                    </label>
                    <button
                      type="button"
                      disabled={!updatePriceEth || parseFloat(updatePriceEth) <= 0}
                      onClick={() => onUpdatePriceConfirm?.(updatePriceEth || '0')}
                      className="rounded-xl border border-emerald-300/20 bg-emerald-300/8 px-3 py-2 text-[11px] uppercase tracking-[0.18em] text-emerald-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {t('marketPanel.confirm')}
                    </button>
                  </div>
                ) : null}
              </>
            ) : (
              <>
                <button
                  type="button"
                  disabled={
                    !wallet.isConnected ||
                    !wallet.isCorrectChain ||
                    actionState === `buy-${item.listingId}`
                  }
                  onClick={onBuy}
                  className="rounded-xl border border-emerald-300/20 bg-emerald-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-emerald-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {actionState === `buy-${item.listingId}` ? t('marketPanel.buying') : t('marketPanel.buy')}
                </button>
                <button
                  type="button"
                  disabled={actionState === `create-offer-${item.nftId}`}
                  onClick={onOfferOpen}
                  className="rounded-xl border border-fuchsia-300/15 bg-fuchsia-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-fuchsia-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {actionState === `create-offer-${item.nftId}` ? t('marketPanel.offering') : t('marketPanel.makeOffer')}
                </button>
                {offerOpen ? (
                  <div className="flex w-full flex-wrap items-end gap-2">
                    <label className="min-w-0 flex-[1_1_100px]">
                      <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-300/60">
                        {t('marketPanel.priceEth')}
                      </span>
                      <input
                        type="number"
                        step="0.001"
                        min="0"
                        value={offerPriceEth}
                        onChange={(e) => onOfferPriceEthChange?.(e.target.value)}
                        placeholder={t('marketPanel.pricePlaceholder')}
                        className="w-full rounded-xl border border-cyan-400/15 bg-[#071523]/80 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/45"
                      />
                    </label>
                    <label className="min-w-0 flex-[1_1_80px]">
                      <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-300/60">
                        {t('marketPanel.expiresHrs')}
                      </span>
                      <input
                        type="number"
                        min="1"
                        value={offerExpirationHours}
                        onChange={(e) => onOfferExpirationHoursChange?.(e.target.value)}
                        placeholder={t('marketPanel.expiresPlaceholder')}
                        className="w-full rounded-xl border border-cyan-400/15 bg-[#071523]/80 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/45"
                      />
                    </label>
                    <button
                      type="button"
                      disabled={!offerPriceEth || parseFloat(offerPriceEth) <= 0}
                      onClick={() => onOfferConfirm?.(item.nftContract || '', item.nftId || 0)}
                      className="rounded-xl border border-emerald-300/20 bg-emerald-300/8 px-3 py-2 text-[11px] uppercase tracking-[0.18em] text-emerald-100 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {t('marketPanel.confirm')}
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


