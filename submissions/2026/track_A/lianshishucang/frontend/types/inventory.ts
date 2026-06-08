export type InventoryLifecycleStatus =
  | 'pending_ai'
  | 'stored'
  | 'failed'
  | 'awaiting_mint'
  | 'minted'
  | 'shipped';

export type InventoryCardStatus = 'pending' | 'generating' | 'completed' | 'failed';

export type InventoryAccentTone = 'cyan' | 'yellow' | 'red' | 'purple' | 'green';
export type InventoryDataSource = 'demo' | 'backend' | 'mixed';
export type InventoryActionKind =
  | 'refresh'
  | 'generate_card'
  | 'prepare_mint'
  | 'view_token_uri'
  | 'upload_collection'
  | 'one_click_convert'
  | 'mint_nft'
  | 'buy_item'
  | 'cancel_listing'
  | 'create_listing'
  | 'update_price'
  | 'place_bid'
  | 'approve_nft'
  | 'approve_all'
  | 'create_offer'
  | 'cancel_offer'
  | 'accept_offer';
export type InventoryNoticeTone = 'info' | 'success' | 'error';

export type InventoryFilterStatus = 'all' | InventoryLifecycleStatus;
export type InventoryCardFilterStatus = 'all' | InventoryCardStatus;
export type InventorySortBy = 'updated_desc' | 'created_desc' | 'name_asc' | 'status';

export interface InventoryAttribute {
  trait_type: string;
  value: string | number;
}

export interface InventoryActionNotice {
  tone: InventoryNoticeTone;
  message: string;
}

export interface InventoryItemViewModel {
  id: string;
  collectionId: number;
  displayCode: string;
  name: string;
  imageUrl: string;
  rawImageUrl?: string;
  aigcBackgroundUrl?: string;
  virtualCardUrl?: string;
  tokenUri?: string;
  status: InventoryLifecycleStatus;
  cardGenerationStatus: InventoryCardStatus;
  statusLabel: string;
  cardStatusLabel: string;
  accentTone: InventoryAccentTone;
  royaltyFee?: number;
  physicalLocation?: string;
  attributes: InventoryAttribute[];
  nftId?: number;
  nftName?: string;
  nftImage?: string;
  createdAt?: string;
  updatedAt?: string;
  hasGeneratedCard: boolean;
  hasMintPrep: boolean;
}

export interface InventoryStats {
  total: number;
  stored: number;
  awaitingMint: number;
  minted: number;
  failed: number;
  generating: number;
}

export interface InventoryDashboardData {
  items: InventoryItemViewModel[];
  stats: InventoryStats;
}

export interface InventoryUploadResult {
  collectionId: number;
  message: string;
}

export interface InventoryConversionState {
  uploadedFileName?: string;
  collectionId?: number;
  uploadStatus: 'idle' | 'uploading' | 'uploaded' | 'failed';
  aiStatus: 'idle' | 'pending' | 'stored' | 'failed';
  cardStatus: InventoryCardStatus | 'idle';
  mintStatus: 'idle' | 'preparing' | 'prepared' | 'failed';
  tokenUri?: string;
}

export interface InventoryFilterOption<T extends string> {
  value: T;
  label: string;
}

export interface BackendUserSummary {
  id?: number;
  nickname?: string;
  wallet_address?: string;
}

export interface BackendNFTSummary {
  id?: number;
  name?: string;
  image?: string;
}

export interface BackendPhysicalCollection {
  id: number;
  user_id?: number;
  name?: string;
  raw_image_url?: string;
  aigc_background_url?: string;
  virtual_card_url?: string;
  token_uri?: string;
  attributes?: unknown;
  status?: string;
  aigc_status?: string;
  card_generation_status?: string;
  royalty_fee?: number;
  physical_location?: string;
  metadata_id?: number;
  nft_id?: number;
  metadata?: {
    id?: number;
    token_uri?: string;
    name?: string;
    description?: string;
    image?: string;
    royalty_fee?: number;
  } | null;
  nft?: BackendNFTSummary | null;
  created_at?: string;
  updated_at?: string;
}

export interface BackendCollectionListResponse {
  collections: BackendPhysicalCollection[];
}

export interface BackendCollectionDetailResponse {
  id: number;
  user_id: number;
  name?: string;
  raw_image_url?: string;
  aigc_status?: string;
  attributes?: unknown;
  created_at?: string;
  updated_at?: string;
}

export interface BackendGenerateCardResponse {
  status: string;
  job_id: number;
}

export interface BackendUploadCollectionResponse {
  code: number;
  message: string;
  collection_id: number;
}

export interface BackendCardStatusResponse {
  id: number;
  card_generation_status: string;
  aigc_background_url?: string;
  virtual_card_url?: string;
}

export interface BackendPrepareMintResponse {
  tokenURI: string;
  royaltyFee: number;
  contractAddress: string;
  status: string;
}

export interface BackendNFT {
  id: number;
  token_id?: number;
  contract_address?: string;
  owner_id?: number;
  creator_id?: number;
  token_uri?: string;
  metadata?: string;
  name?: string;
  description?: string;
  image?: string;
  royalty_fee?: number;
  tx_hash?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  owner?: BackendUserSummary;
  creator?: BackendUserSummary;
}

export interface BackendNFTListResponse {
  nfts: BackendNFT[];
  total: number;
  page: number;
}

export interface BackendMarketplaceListing {
  id: number;
  nft_id?: number;
  seller_id?: number;
  listing_id?: number;
  price_wei: string;
  status?: string;
  tx_hash?: string;
  created_at?: string;
  updated_at?: string;
  nft?: BackendNFT | null;
  seller?: BackendUserSummary;
}

export interface BackendMarketplaceListingListResponse {
  listings: BackendMarketplaceListing[];
  total: number;
  page: number;
}



export interface InventoryMarketListingViewModel {
  id: string;
  listingId: string;
  nftId?: number;
  nftContract?: string;
  title: string;
  imageUrl: string;
  sellerLabel: string;
  priceWei: string;
  priceEthLabel: string;
  status: string;
  createdAt?: string;
  isSelectedItemMatch: boolean;
}

export interface InventoryMarketNftViewModel {
  id: number;
  tokenId: string;
  name: string;
  imageUrl: string;
  tokenUri?: string;
  ownerLabel?: string;
  creatorLabel?: string;
  royaltyFeeLabel?: string;
  status: string;
}

export interface InventoryMarketSummary {
  activeListings: number;
  ownedNfts: number;
  createdNfts: number;
  selectedItemListed: boolean;
}

export interface InventoryMarketOfferViewModel {
  id: string;
  offerId: string;
  tokenId: number;
  nftContract: string;
  bidder: string;
  bidderLabel: string;
  priceWei: string;
  priceEthLabel: string;
  expiration: number;
  active: boolean;
  createdAt: number;
  isExpired: boolean;
}

export interface InventoryMarketData {
  listings: InventoryMarketListingViewModel[];
  selectedNft: InventoryMarketNftViewModel | null;
  summary: InventoryMarketSummary;
}
