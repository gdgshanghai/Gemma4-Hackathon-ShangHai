package models

import (
	"encoding/json"
	"math/big"
	"time"

	"gorm.io/gorm"
)

const (
	PhysicalCollectionStatusPendingAI    = "PENDING_AI"
	PhysicalCollectionStatusStored       = "STORED"
	PhysicalCollectionStatusFailed       = "FAILED"
	PhysicalCollectionStatusAwaitingMint = "AWAITING_MINT"
	PhysicalCollectionStatusMinted       = "MINTED"
	PhysicalCollectionStatusShipped      = "SHIPPED"

	PhysicalCollectionCardStatusPending    = "PENDING"
	PhysicalCollectionCardStatusGenerating = "GENERATING"
	PhysicalCollectionCardStatusCompleted  = "COMPLETED"
	PhysicalCollectionCardStatusFailed     = "FAILED"
)

type User struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	WalletAddress string    `gorm:"uniqueIndex;size:42;not null" json:"wallet_address"`
	Nickname      string    `gorm:"size:100" json:"nickname"`
	Avatar        string    `gorm:"size:500" json:"avatar"`
	Bio           string    `gorm:"size:500" json:"bio"`
	Nonce         string    `gorm:"size:100" json:"-"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
	NFTs          []NFT     `gorm:"foreignKey:OwnerID" json:"nfts,omitempty"`
}

type NFT struct {
	ID              uint      `gorm:"primaryKey" json:"id"`
	TokenID         uint64    `gorm:"uniqueIndex:idx_contract_token;not null" json:"token_id"`
	ContractAddress string    `gorm:"uniqueIndex:idx_contract_token;size:42;not null" json:"contract_address"`
	OwnerID         uint      `gorm:"index;not null" json:"owner_id"`
	CreatorID       uint      `gorm:"index;not null" json:"creator_id"`
	TokenURI        string    `gorm:"size:2000" json:"token_uri"`
	Metadata        string    `gorm:"type:text" json:"metadata"`
	Name            string    `gorm:"size:200" json:"name"`
	Description     string    `gorm:"type:text" json:"description"`
	Image           string    `gorm:"size:2000" json:"image"`
	RoyaltyFee      uint64    `json:"royalty_fee"`
	TxHash          string    `gorm:"size:66;index" json:"tx_hash"`
	Status          string    `gorm:"size:20;default:active" json:"status"`
	CreatedAt       time.Time `json:"created_at"`
	UpdatedAt       time.Time `json:"updated_at"`
	Owner           User      `gorm:"foreignKey:OwnerID" json:"owner,omitempty"`
	Creator         User      `gorm:"foreignKey:CreatorID" json:"creator,omitempty"`
}

type Listing struct {
	ID        uint           `gorm:"primaryKey" json:"id"`
	NFTID     uint           `gorm:"index;not null" json:"nft_id"`
	SellerID  uint           `gorm:"index;not null" json:"seller_id"`
	ListingID uint64         `json:"listing_id"`
	Price     *big.Int       `gorm:"-:all" json:"price"`
	PriceWei  string         `gorm:"size:78;not null" json:"price_wei"`
	Status    string         `gorm:"size:20;default:active" json:"status"`
	TxHash    string         `gorm:"size:66" json:"tx_hash"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
	DeletedAt gorm.DeletedAt `gorm:"index" json:"-"`
	NFT       NFT            `gorm:"foreignKey:NFTID" json:"nft,omitempty"`
	Seller    User           `gorm:"foreignKey:SellerID" json:"seller,omitempty"`
}

type Offer struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	NFTID      uint      `gorm:"index;not null" json:"nft_id"`
	BidderID   uint      `gorm:"index;not null" json:"bidder_id"`
	OfferID    uint64    `json:"offer_id"`
	Price      string    `gorm:"size:78;not null" json:"price_wei"`
	Expiration time.Time `json:"expiration"`
	Status     string    `gorm:"size:20;default:active" json:"status"`
	TxHash     string    `gorm:"size:66" json:"tx_hash"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
	NFT        NFT       `gorm:"foreignKey:NFTID" json:"nft,omitempty"`
	Bidder     User      `gorm:"foreignKey:BidderID" json:"bidder,omitempty"`
}

type Transaction struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	TxHash    string    `gorm:"size:66;index" json:"tx_hash"`
	FromID    uint      `gorm:"index" json:"from_id"`
	ToID      uint      `gorm:"index" json:"to_id"`
	NFTID     *uint     `json:"nft_id"`
	Type      string    `gorm:"size:30;not null" json:"type"`
	Amount    string    `gorm:"size:78" json:"amount_wei"`
	Status    string    `gorm:"size:20;default:pending" json:"status"`
	CreatedAt time.Time `json:"created_at"`
	From      User      `gorm:"foreignKey:FromID" json:"from,omitempty"`
	To        User      `gorm:"foreignKey:ToID" json:"to,omitempty"`
	NFT       *NFT      `gorm:"foreignKey:NFTID" json:"nft,omitempty"`
}

type NFTMetadata struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	UserID      uint      `gorm:"index;not null" json:"user_id"`
	TokenURI    string    `gorm:"uniqueIndex;size:2000;not null" json:"token_uri"`
	Name        string    `gorm:"size:200" json:"name"`
	Description string    `gorm:"type:text" json:"description"`
	Image       string    `gorm:"size:2000" json:"image"`
	RoyaltyFee  uint64    `json:"royalty_fee"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
	User        User      `gorm:"foreignKey:UserID" json:"user,omitempty"`
}

type PhysicalCollection struct {
	ID                   uint            `gorm:"primaryKey" json:"id"`
	UserID               uint            `gorm:"index;not null" json:"user_id"`
	Name                 string          `gorm:"size:200" json:"name"`
	MetadataID           *uint           `gorm:"index" json:"metadata_id,omitempty"`
	NFTID                *uint           `gorm:"index" json:"nft_id,omitempty"`
	RawImageURL          string          `gorm:"size:2000;not null" json:"raw_image_url"`
	AIGCBackgroundURL    string          `gorm:"size:2000" json:"aigc_background_url"`
	VirtualCardURL       string          `gorm:"size:2000" json:"virtual_card_url"`
	TokenURI             string          `gorm:"size:2000;index" json:"token_uri"`
	Attributes           json.RawMessage `gorm:"type:jsonb" json:"attributes"`
	Status               string          `gorm:"size:20;index;not null" json:"status"`
	CardGenerationStatus string          `gorm:"size:20;index;not null" json:"card_generation_status"`
	RoyaltyFee           uint64          `json:"royalty_fee"`
	PhysicalLocation     string          `gorm:"size:255" json:"physical_location"`
	CreatedAt            time.Time       `json:"created_at"`
	UpdatedAt            time.Time       `json:"updated_at"`
	DeletedAt            gorm.DeletedAt  `gorm:"index" json:"-"`
	User                 User            `gorm:"foreignKey:UserID" json:"user,omitempty"`
	Metadata             *NFTMetadata    `gorm:"foreignKey:MetadataID" json:"metadata,omitempty"`
	NFT                  *NFT            `gorm:"foreignKey:NFTID" json:"nft,omitempty"`
}

type Activity struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	NFTID     *uint     `gorm:"index" json:"nft_id"`
	UserID    uint      `gorm:"index" json:"user_id"`
	Action    string    `gorm:"size:30;not null" json:"action"`
	Detail    string    `gorm:"type:text" json:"detail"`
	TxHash    string    `gorm:"size:66" json:"tx_hash"`
	CreatedAt time.Time `json:"created_at"`
	User      User      `gorm:"foreignKey:UserID" json:"user,omitempty"`
	NFT       *NFT      `gorm:"foreignKey:NFTID" json:"nft,omitempty"`
}
