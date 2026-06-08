package handlers

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/services"
	"gorm.io/gorm"
)

type MarketplaceHandler struct {
	db                 *gorm.DB
	cfg                *config.Config
	marketplaceService *services.MarketplaceService
}

func NewMarketplaceHandler(db *gorm.DB, cfg *config.Config, marketplaceService *services.MarketplaceService) *MarketplaceHandler {
	return &MarketplaceHandler{db: db, cfg: cfg, marketplaceService: marketplaceService}
}

func (h *MarketplaceHandler) ListListings(c *gin.Context) {
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	pageSize, _ := strconv.Atoi(c.DefaultQuery("page_size", "20"))
	if pageSize > 100 {
		pageSize = 100
	}

	listings, total, err := h.marketplaceService.ListActiveListings(page, pageSize)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch listings"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"listings": listings,
		"total":    total,
		"page":     page,
	})
}

func (h *MarketplaceHandler) GetListing(c *gin.Context) {
	id, err := strconv.ParseUint(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid listing ID"})
		return
	}

	listing, err := h.marketplaceService.GetListing(uint(id))
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "listing not found"})
		return
	}

	c.JSON(http.StatusOK, listing)
}
