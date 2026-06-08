package handlers

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"github.com/lianshishucang/backend/services"
	"gorm.io/gorm"
)

type NFTHandler struct {
	db         *gorm.DB
	cfg        *config.Config
	nftService *services.NFTService
}

func NewNFTHandler(db *gorm.DB, cfg *config.Config, nftService *services.NFTService) *NFTHandler {
	return &NFTHandler{db: db, cfg: cfg, nftService: nftService}
}

type RegisterMetadataRequest struct {
	TokenURI    string `json:"token_uri"`
	Name        string `json:"name" binding:"required"`
	Description string `json:"description"`
	Image       string `json:"image" binding:"required"`
	RoyaltyFee  uint64 `json:"royalty_fee"`
}

func (h *NFTHandler) RegisterMetadata(c *gin.Context) {
	userID := c.GetUint("user_id")

	var req RegisterMetadataRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.RoyaltyFee > 1000 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "royalty fee cannot exceed 10% (1000 bps)"})
		return
	}

	if req.TokenURI == "" {
		idBytes := make([]byte, 16)
		rand.Read(idBytes)
		req.TokenURI = "https://" + h.cfg.ServerPort + "/v1/metadata/" + hex.EncodeToString(idBytes)
	}

	meta := &models.NFTMetadata{
		UserID:      userID,
		TokenURI:    req.TokenURI,
		Name:        req.Name,
		Description: req.Description,
		Image:       req.Image,
		RoyaltyFee:  req.RoyaltyFee,
	}
	if err := h.db.Create(meta).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to register metadata"})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"message":   "metadata registered",
		"id":        meta.ID,
		"token_uri": meta.TokenURI,
		"metadata":  meta,
	})
}

func (h *NFTHandler) ListNFTs(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	if pageSize > 100 {
		pageSize = 100
	}

	nfts, total, err := h.nftService.ListNFTs(page, pageSize, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch NFTs"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"nfts":  nfts,
		"total": total,
		"page":  page,
	})
}

func (h *NFTHandler) GetNFT(c *gin.Context) {
	id, err := strconv.ParseUint(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid NFT ID"})
		return
	}

	nft, err := h.nftService.GetNFT(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "NFT not found"})
		return
	}

	c.JSON(http.StatusOK, nft)
}

func (h *NFTHandler) GetMyNFTs(c *gin.Context) {
	userID := c.GetUint("user_id")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	if pageSize > 100 {
		pageSize = 100
	}

	nfts, total, err := h.nftService.GetNFTsByOwner(userID, page, pageSize)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch NFTs"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"nfts":  nfts,
		"total": total,
		"page":  page,
	})
}

func (h *NFTHandler) GetCreatedNFTs(c *gin.Context) {
	userID := c.GetUint("user_id")
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	if pageSize > 100 {
		pageSize = 100
	}

	nfts, total, err := h.nftService.GetNFTsByCreator(userID, page, pageSize)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch NFTs"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"nfts":  nfts,
		"total": total,
		"page":  page,
	})
}
