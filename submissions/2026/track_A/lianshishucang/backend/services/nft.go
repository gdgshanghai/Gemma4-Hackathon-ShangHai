package services

import (
	"math/big"

	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"gorm.io/gorm"
)

type NFTService struct {
	db      *gorm.DB
	cfg     *config.Config
	blockchain *BlockchainService
}

func NewNFTService(db *gorm.DB, cfg *config.Config, blockchain *BlockchainService) *NFTService {
	return &NFTService{db: db, cfg: cfg, blockchain: blockchain}
}

func (s *NFTService) ListNFTs(page, pageSize int, ownerID *uint) ([]models.NFT, int64, error) {
	var nfts []models.NFT
	var total int64
	query := s.db.Model(&models.NFT{})

	if ownerID != nil {
		query = query.Where("owner_id = ?", *ownerID)
	}

	query.Count(&total)

	err := query.
		Preload("Owner").
		Preload("Creator").
		Order("created_at DESC").
		Offset((page - 1) * pageSize).
		Limit(pageSize).
		Find(&nfts).Error

	return nfts, total, err
}

func (s *NFTService) GetNFT(id uint) (*models.NFT, error) {
	var nft models.NFT
	err := s.db.Preload("Owner").Preload("Creator").First(&nft, id).Error
	if err != nil {
		return nil, err
	}
	return &nft, nil
}

func (s *NFTService) GetNFTByToken(tokenID uint64, contractAddr string) (*models.NFT, error) {
	var nft models.NFT
	err := s.db.Where("token_id = ? AND contract_address = ?", tokenID, contractAddr).
		Preload("Owner").Preload("Creator").
		First(&nft).Error
	if err != nil {
		return nil, err
	}
	return &nft, nil
}

func (s *NFTService) CreateNFT(nft *models.NFT) error {
	return s.db.Create(nft).Error
}

func (s *NFTService) UpdateNFTOwner(tokenID uint64, contractAddr string, newOwnerID uint) error {
	return s.db.Model(&models.NFT{}).
		Where("token_id = ? AND contract_address = ?", tokenID, contractAddr).
		Update("owner_id", newOwnerID).Error
}

func (s *NFTService) MintNFT(
	ownerID uint,
	creatorID uint,
	tokenID uint64,
	tokenURI string,
	name string,
	description string,
	image string,
	royaltyFee uint64,
	txHash string,
) (*models.NFT, error) {

	nft := &models.NFT{
		TokenID:         tokenID,
		ContractAddress: s.blockchain.GetNFTAddress().Hex(),
		OwnerID:         ownerID,
		CreatorID:       creatorID,
		TokenURI:        tokenURI,
		Metadata:        tokenURI,
		Name:            name,
		Description:     description,
		Image:           image,
		RoyaltyFee:      royaltyFee,
		TxHash:          txHash,
		Status:          "active",
	}

	if err := s.db.Create(nft).Error; err != nil {
		return nil, err
	}
	return nft, nil
}

func (s *NFTService) GetNFTsByOwner(ownerID uint, page, pageSize int) ([]models.NFT, int64, error) {
	return s.ListNFTs(page, pageSize, &ownerID)
}

func (s *NFTService) GetNFTsByCreator(creatorID uint, page, pageSize int) ([]models.NFT, int64, error) {
	var nfts []models.NFT
	var total int64

	query := s.db.Model(&models.NFT{}).Where("creator_id = ?", creatorID)
	query.Count(&total)

	err := query.
		Preload("Owner").
		Preload("Creator").
		Order("created_at DESC").
		Offset((page - 1) * pageSize).
		Limit(pageSize).
		Find(&nfts).Error

	return nfts, total, err
}

func (s *NFTService) TransferNFT(nftID uint, fromID, toID uint, txHash string) error {
	nft, err := s.GetNFT(nftID)
	if err != nil {
		return err
	}

	if nft.OwnerID != fromID {
		return nil
	}

	return s.db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&models.NFT{}).Where("id = ?", nftID).Update("owner_id", toID).Error; err != nil {
			return err
		}

		txLog := &models.Transaction{
			TxHash: txHash,
			FromID: fromID,
			ToID:   toID,
			NFTID:  &nftID,
			Type:   "transfer",
			Amount: "0",
			Status: "confirmed",
		}
		return tx.Create(txLog).Error
	})
}

func (s *NFTService) logActivity(nftID *uint, userID uint, action, detail, txHash string) {
	s.db.Create(&models.Activity{
		NFTID:   nftID,
		UserID:  userID,
		Action:  action,
		Detail:  detail,
		TxHash:  txHash,
	})
}

func weiToEther(wei *big.Int) *big.Float {
	return new(big.Float).Quo(new(big.Float).SetInt(wei), big.NewFloat(1e18))
}

func etherToWei(ether *big.Float) *big.Int {
	wei, _ := new(big.Float).Mul(ether, big.NewFloat(1e18)).Int(nil)
	return wei
}
