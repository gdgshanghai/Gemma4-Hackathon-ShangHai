import i18n from '../../lib/i18n/i18n';
import {
  CARD_STATUS_LABELS,
  STATUS_ACCENTS,
  STATUS_LABELS,
} from './constants';
import type {
  BackendCardStatusResponse,
  BackendMarketplaceListing,
  BackendNFT,
  BackendPhysicalCollection,
  BackendUserSummary,
  InventoryAttribute,
  InventoryCardStatus,
  InventoryDashboardData,
  InventoryItemViewModel,
  InventoryLifecycleStatus,
  InventoryMarketListingViewModel,
  InventoryMarketNftViewModel,
  InventoryMarketSummary,
  InventoryStats,
} from '../../types/inventory';

const BACKEND_STATUS_MAP: Record<string, InventoryLifecycleStatus> = {
  PENDING_AI: 'pending_ai',
  STORED: 'stored',
  FAILED: 'failed',
  AWAITING_MINT: 'awaiting_mint',
  MINTED: 'minted',
  SHIPPED: 'shipped',
};

const BACKEND_CARD_STATUS_MAP: Record<string, InventoryCardStatus> = {
  PENDING: 'pending',
  GENERATING: 'generating',
  COMPLETED: 'completed',
  FAILED: 'failed',
};

export function toInventoryStatus(status?: string): InventoryLifecycleStatus {
  return BACKEND_STATUS_MAP[(status ?? '').trim().toUpperCase()] ?? 'stored';
}

export function toInventoryCardStatus(status?: string): InventoryCardStatus {
  return BACKEND_CARD_STATUS_MAP[(status ?? '').trim().toUpperCase()] ?? 'pending';
}

export function parseInventoryAttributes(input: unknown): InventoryAttribute[] {
  if (!input) {
    return [];
  }

  const parsed = typeof input === 'string' ? safeJsonParse(input) : input;
  const source = Array.isArray(parsed)
    ? parsed
    : parsed && typeof parsed === 'object'
      ? normalizeObjectAttributes(parsed as Record<string, unknown>)
      : [];

  return source
    .map((entry) => {
      if (!entry || typeof entry !== 'object') {
        return null;
      }

      const record = entry as Record<string, unknown>;
      const traitType =
        typeof record.trait_type === 'string'
          ? record.trait_type
          : typeof record.label === 'string'
            ? record.label
            : typeof record.key === 'string'
              ? record.key
              : '';

      const value = record.value;
      if (!traitType || (typeof value !== 'string' && typeof value !== 'number')) {
        return null;
      }

      return {
        trait_type: startCase(traitType),
        value,
      } satisfies InventoryAttribute;
    })
    .filter((entry): entry is InventoryAttribute => Boolean(entry));
}

export function adaptCollectionToInventoryItem(
  collection: BackendPhysicalCollection,
): InventoryItemViewModel {
  const status = toInventoryStatus(collection.status || collection.aigc_status);
  const cardGenerationStatus = toInventoryCardStatus(collection.card_generation_status);
  const attributes = parseInventoryAttributes(collection.attributes);

  return {
    id: String(collection.id),
    collectionId: collection.id,
    displayCode: `COL-${String(collection.id).padStart(4, '0')}`,
    name: collection.name?.trim() || i18n.t('adapters.untitledCollectible'),
    imageUrl:
      collection.virtual_card_url?.trim() ||
      collection.raw_image_url?.trim() ||
      'https://placehold.co/600x600/0a192f/67e8f9?text=NO+SIGNAL',
    rawImageUrl: collection.raw_image_url?.trim() || undefined,
    aigcBackgroundUrl: collection.aigc_background_url?.trim() || undefined,
    virtualCardUrl: collection.virtual_card_url?.trim() || undefined,
    tokenUri: collection.token_uri?.trim() || collection.metadata?.token_uri?.trim() || undefined,
    status,
    cardGenerationStatus,
    statusLabel: STATUS_LABELS[status],
    cardStatusLabel: CARD_STATUS_LABELS[cardGenerationStatus],
    accentTone: STATUS_ACCENTS[status],
    royaltyFee: collection.royalty_fee ?? collection.metadata?.royalty_fee,
    physicalLocation: collection.physical_location?.trim() || undefined,
    attributes,
    nftId: collection.nft_id ?? collection.nft?.id,
    nftName: collection.nft?.name?.trim() || undefined,
    nftImage: collection.nft?.image?.trim() || undefined,
    createdAt: collection.created_at,
    updatedAt: collection.updated_at,
    hasGeneratedCard: cardGenerationStatus === 'completed' && Boolean(collection.virtual_card_url),
    hasMintPrep: Boolean(collection.token_uri || collection.metadata?.token_uri),
  };
}

export function adaptCollectionDetailPatch(
  item: InventoryItemViewModel,
  patch: Partial<BackendPhysicalCollection>,
): InventoryItemViewModel {
  return adaptCollectionToInventoryItem({
    id: item.collectionId,
    name: item.name,
    raw_image_url: item.rawImageUrl,
    aigc_background_url: item.aigcBackgroundUrl,
    virtual_card_url: item.virtualCardUrl,
    token_uri: item.tokenUri,
    attributes: item.attributes.map((attribute) => ({
      trait_type: attribute.trait_type,
      value: attribute.value,
    })),
    status: reverseStatusLabel(item.status),
    card_generation_status: reverseCardStatus(item.cardGenerationStatus),
    royalty_fee: item.royaltyFee,
    physical_location: item.physicalLocation,
    nft_id: item.nftId,
    nft: item.nftId
      ? {
          id: item.nftId,
          name: item.nftName,
          image: item.nftImage,
        }
      : null,
    created_at: item.createdAt,
    updated_at: item.updatedAt,
    ...patch,
  });
}

export function adaptCardStatusIntoItem(
  item: InventoryItemViewModel,
  status: BackendCardStatusResponse,
): InventoryItemViewModel {
  return adaptCollectionDetailPatch(item, {
    card_generation_status: status.card_generation_status,
    aigc_background_url: status.aigc_background_url,
    virtual_card_url: status.virtual_card_url,
  });
}

export function adaptBackendNFTToDetailViewModel(
  nft: BackendNFT,
): InventoryMarketNftViewModel {
  return {
    id: nft.id,
    tokenId: nft.token_id ? `#${nft.token_id}` : 'Pending',
    name: nft.name?.trim() || i18n.t('adapters.untitledNft'),
    imageUrl: resolveTradingImage(nft.image),
    tokenUri: nft.token_uri?.trim() || undefined,
    ownerLabel: formatWalletLabel(nft.owner),
    creatorLabel: formatWalletLabel(nft.creator),
    royaltyFeeLabel: nft.royalty_fee ? `${(nft.royalty_fee / 100).toFixed(2)}%` : '—',
    status: nft.status?.trim() || 'unknown',
  };
}

export function adaptListingToMarketListingViewModel(
  listing: BackendMarketplaceListing,
  selectedNftId?: number,
): InventoryMarketListingViewModel {
  return {
    id: String(listing.id),
    listingId: String(listing.listing_id ?? listing.id),
    nftId: listing.nft_id ?? listing.nft?.id,
    nftContract: listing.nft?.contract_address || undefined,
    title: listing.nft?.name?.trim() || i18n.t('adapters.untitledListing'),
    imageUrl: resolveTradingImage(listing.nft?.image),
    sellerLabel: formatWalletLabel(listing.seller),
    priceWei: listing.price_wei,
    priceEthLabel: formatWeiToEthLabel(listing.price_wei),
    status: startCase(listing.status || 'active'),
    createdAt: listing.created_at,
    isSelectedItemMatch: Boolean(selectedNftId) && (listing.nft_id ?? listing.nft?.id) === selectedNftId,
  };
}

export function buildInventoryMarketSummary(input: {
  listings: InventoryMarketListingViewModel[];
  ownedNfts: number;
  createdNfts: number;
  selectedNftId?: number;
}): InventoryMarketSummary {
  return {
    activeListings: input.listings.length,
    ownedNfts: input.ownedNfts,
    createdNfts: input.createdNfts,
    selectedItemListed: Boolean(
      input.selectedNftId && input.listings.some((listing) => listing.nftId === input.selectedNftId),
    ),
  };
}

export function buildInventoryStats(items: InventoryItemViewModel[]): InventoryStats {
  return {
    total: items.length,
    stored: items.filter((item) => item.status === 'stored').length,
    awaitingMint: items.filter((item) => item.status === 'awaiting_mint').length,
    minted: items.filter((item) => item.status === 'minted').length,
    failed: items.filter(
      (item) => item.status === 'failed' || item.cardGenerationStatus === 'failed',
    ).length,
    generating: items.filter((item) => item.cardGenerationStatus === 'generating').length,
  };
}

export function buildInventoryDashboardData(items: InventoryItemViewModel[]): InventoryDashboardData {
  return {
    items,
    stats: buildInventoryStats(items),
  };
}

function normalizeObjectAttributes(
  input: Record<string, unknown>,
): Array<Record<string, unknown>> {
  return Object.entries(input)
    .filter(([, value]) => typeof value === 'string' || typeof value === 'number')
    .map(([key, value]) => ({ trait_type: key, value }));
}

function safeJsonParse(input: string): unknown {
  try {
    return JSON.parse(input);
  } catch {
    return [];
  }
}

function startCase(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function reverseStatusLabel(status: InventoryLifecycleStatus): string {
  switch (status) {
    case 'pending_ai':
      return 'PENDING_AI';
    case 'stored':
      return 'STORED';
    case 'failed':
      return 'FAILED';
    case 'awaiting_mint':
      return 'AWAITING_MINT';
    case 'minted':
      return 'MINTED';
    case 'shipped':
      return 'SHIPPED';
    default:
      return 'STORED';
  }
}

function reverseCardStatus(status: InventoryCardStatus): string {
  switch (status) {
    case 'pending':
      return 'PENDING';
    case 'generating':
      return 'GENERATING';
    case 'completed':
      return 'COMPLETED';
    case 'failed':
      return 'FAILED';
    default:
      return 'PENDING';
  }
}

function formatWeiToEthLabel(wei: string): string {
  try {
    const value = BigInt(wei || '0');
    const whole = value / 1000000000000000000n;
    const fraction = value % 1000000000000000000n;
    const fractionString = fraction.toString().padStart(18, '0').slice(0, 4).replace(/0+$/, '');
    return fractionString ? `${whole}.${fractionString}${i18n.t('adapters.ethUnit')}` : `${whole}${i18n.t('adapters.ethUnit')}`;
  } catch {
    return '—';
  }
}

function formatWalletLabel(user?: BackendUserSummary | null): string {
  if (!user) {
    return i18n.t('common.unknown');
  }

  if (user.nickname?.trim()) {
    return user.nickname.trim();
  }

  if (user.wallet_address) {
    return truncateWallet(user.wallet_address);
  }

  return user.id ? i18n.t('adapters.userPrefix', { id: user.id }) : i18n.t('common.unknown');
}

function truncateWallet(wallet: string): string {
  if (wallet.length <= 12) {
    return wallet;
  }

  return `${wallet.slice(0, 6)}...${wallet.slice(-4)}`;
}

function resolveTradingImage(image?: string): string {
  return image?.trim() || 'https://placehold.co/400x400/0a192f/67e8f9?text=NFT';
}

function formatTimeStateLabel(endTime?: string): string {
  if (!endTime) {
    return i18n.t('adapters.noEndTime');
  }

  const endTimestamp = Date.parse(endTime);
  if (Number.isNaN(endTimestamp)) {
    return i18n.t('adapters.invalidEndTime');
  }

  const deltaMs = endTimestamp - Date.now();
  if (deltaMs <= 0) {
    return i18n.t('adapters.ended');
  }

  const hours = Math.floor(deltaMs / (1000 * 60 * 60));
  if (hours >= 24) {
    return i18n.t('adapters.daysLeft', { count: Math.ceil(hours / 24) });
  }

  if (hours >= 1) {
    return i18n.t('adapters.hoursLeft', { count: hours });
  }

  const minutes = Math.max(1, Math.floor(deltaMs / (1000 * 60)));
  return i18n.t('adapters.minutesLeft', { count: minutes });
}
