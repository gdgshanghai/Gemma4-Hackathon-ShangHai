package services

import (
	"math/big"

	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"gorm.io/gorm"
)

type MarketplaceService struct {
	db         *gorm.DB
	cfg        *config.Config
	nftService *NFTService
}

func NewMarketplaceService(db *gorm.DB, cfg *config.Config, nftService *NFTService) *MarketplaceService {
	return &MarketplaceService{db: db, cfg: cfg, nftService: nftService}
}

func (s *MarketplaceService) ListActiveListings(page, pageSize int) ([]models.Listing, int64, error) {
	var listings []models.Listing
	var total int64

	query := s.db.Model(&models.Listing{}).Where("status = ?", "active")
	query.Count(&total)

	err := query.
		Preload("NFT").
		Preload("NFT.Owner").
		Preload("NFT.Creator").
		Preload("Seller").
		Order("created_at DESC").
		Offset((page - 1) * pageSize).
		Limit(pageSize).
		Find(&listings).Error

	return listings, total, err
}

func (s *MarketplaceService) GetListing(id uint) (*models.Listing, error) {
	var listing models.Listing
	err := s.db.Preload("NFT").Preload("Seller").First(&listing, id).Error
	if err != nil {
		return nil, err
	}
	return &listing, nil
}

func (s *MarketplaceService) GetListingsBySeller(sellerID uint, page, pageSize int) ([]models.Listing, int64, error) {
	var listings []models.Listing
	var total int64

	query := s.db.Model(&models.Listing{}).Where("seller_id = ?", sellerID)
	query.Count(&total)

	err := query.
		Preload("NFT").
		Preload("Seller").
		Order("created_at DESC").
		Offset((page - 1) * pageSize).
		Limit(pageSize).
		Find(&listings).Error

	return listings, total, err
}

func (s *MarketplaceService) GetListingsByNFT(nftID uint) (*models.Listing, error) {
	var listing models.Listing
	err := s.db.Where("nft_id = ? AND status = ?", nftID, "active").
		Preload("NFT").Preload("Seller").
		First(&listing).Error
	if err != nil {
		return nil, err
	}
	return &listing, nil
}

func (s *MarketplaceService) CreateListing(nftID, sellerID uint, price *big.Int, txHash string) (*models.Listing, error) {
	listing := &models.Listing{
		NFTID:    nftID,
		SellerID: sellerID,
		PriceWei: price.String(),
		Status:   "active",
		TxHash:   txHash,
	}

	if err := s.db.Create(listing).Error; err != nil {
		return nil, err
	}

	s.nftService.logActivity(&nftID, sellerID, "listing_created", "price: "+price.String()+" wei", txHash)
	return listing, nil
}

func (s *MarketplaceService) CancelListing(listingID, userID uint) error {
	listing, err := s.GetListing(listingID)
	if err != nil {
		return err
	}

	if listing.SellerID != userID {
		return nil
	}

	return s.db.Model(&models.Listing{}).Where("id = ?", listingID).
		Update("status", "cancelled").Error
}

func (s *MarketplaceService) CompleteSale(listingID, buyerID uint) error {
	listing, err := s.GetListing(listingID)
	if err != nil {
		return err
	}

	return s.db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&models.Listing{}).Where("id = ?", listingID).
			Update("status", "sold").Error; err != nil {
			return err
		}

		if err := tx.Model(&models.NFT{}).Where("id = ?", listing.NFTID).
			Update("owner_id", buyerID).Error; err != nil {
			return err
		}

		txLog := &models.Transaction{
			FromID: listing.SellerID,
			ToID:   buyerID,
			NFTID:  &listing.NFTID,
			Type:   "purchase",
			Amount: listing.PriceWei,
			Status: "confirmed",
		}

		if err := tx.Create(txLog).Error; err != nil {
			return err
		}

		s.nftService.logActivity(&listing.NFTID, buyerID, "purchase", "price: "+listing.PriceWei+" wei", "")
		return nil
	})
}
