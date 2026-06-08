package handlers

import (
	"context"
	"errors"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"github.com/lianshishucang/backend/services"
	"gorm.io/gorm"
)

type AIGCHandler struct {
	db                 *gorm.DB
	cfg                *config.Config
	aigcService        *services.AIGCService
	compositingService *services.CompositingService
}

type GenerateCardRequest struct {
	StylePrompt string `json:"style_prompt" binding:"required"`
}

func NewAIGCHandler(db *gorm.DB, cfg *config.Config, aigcService *services.AIGCService, compositingService *services.CompositingService) *AIGCHandler {
	return &AIGCHandler{db: db, cfg: cfg, aigcService: aigcService, compositingService: compositingService}
}

func (h *AIGCHandler) GenerateCard(c *gin.Context) {
	userID := c.GetUint("user_id")
	collectionID, err := strconv.ParseUint(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid collection ID"})
		return
	}

	var req GenerateCardRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	req.StylePrompt = strings.TrimSpace(req.StylePrompt)
	if req.StylePrompt == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "style_prompt is required"})
		return
	}

	collection, err := h.findUserCollection(uint(collectionID), userID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "collection not found"})
			return
		}
		log.Printf("[aigc] failed to load collection: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load collection"})
		return
	}
	if collection.Status != models.PhysicalCollectionStatusStored {
		c.JSON(http.StatusBadRequest, gin.H{"error": "collection is not ready for card generation"})
		return
	}
	if len(collection.Attributes) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "collection attributes are missing"})
		return
	}

	result := h.db.Model(&models.PhysicalCollection{}).
		Where("id = ? AND user_id = ?", collection.ID, userID).
		Updates(map[string]interface{}{
			"card_generation_status": models.PhysicalCollectionCardStatusGenerating,
			"aigc_background_url":    "",
			"virtual_card_url":       "",
		})
	if result.Error != nil {
		log.Printf("[aigc] failed to mark collection generating: %v", result.Error)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to start card generation"})
		return
	}

	go h.generateCardAsync(collection.ID, userID, req.StylePrompt)

	c.JSON(http.StatusAccepted, gin.H{
		"status": "processing",
		"job_id": collection.ID,
	})
}

func (h *AIGCHandler) GetCardStatus(c *gin.Context) {
	userID := c.GetUint("user_id")
	collectionID, err := strconv.ParseUint(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid collection ID"})
		return
	}

	collection, err := h.findUserCollection(uint(collectionID), userID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "collection not found"})
			return
		}
		log.Printf("[aigc] failed to load collection status: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch card status"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":                     collection.ID,
		"card_generation_status": collection.CardGenerationStatus,
		"aigc_background_url":    collection.AIGCBackgroundURL,
		"virtual_card_url":       collection.VirtualCardURL,
	})
}

func (h *AIGCHandler) generateCardAsync(collectionID, userID uint, stylePrompt string) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	collection, err := h.findUserCollectionWithContext(ctx, collectionID, userID)
	if err != nil {
		log.Printf("[aigc] failed to load collection %d: %v", collectionID, err)
		h.markCardFailed(ctx, collectionID, userID, "")
		return
	}

	backgroundURL, err := h.aigcService.GenerateStylizedBackground(ctx, collectionID, stylePrompt)
	if err != nil {
		log.Printf("[aigc] failed to generate background for collection %d: %v, using raw image", collectionID, err)
		backgroundURL = collection.RawImageURL
	}

	metadata, err := buildCardMetadata(collection)
	if err != nil {
		log.Printf("[aigc] failed to build card metadata for collection %d: %v, using defaults", collectionID, err)
		metadata = services.CardMetadata{
			Name:     "Collectible Card",
			IP:       "",
			Rarity:   "Collector",
			Material: "",
		}
	}

	cardURL, err := h.compositingService.RenderVirtualCard(ctx, backgroundURL, collection.RawImageURL, metadata)
	if err != nil {
		log.Printf("[aigc] failed to render virtual card for collection %d: %v, using raw image as card", collectionID, err)
		cardURL = collection.RawImageURL
	}

	if err := h.db.WithContext(ctx).
		Model(&models.PhysicalCollection{}).
		Where("id = ? AND user_id = ?", collectionID, userID).
		Updates(map[string]interface{}{
			"aigc_background_url":    backgroundURL,
			"virtual_card_url":       cardURL,
			"card_generation_status": models.PhysicalCollectionCardStatusCompleted,
		}).Error; err != nil {
		log.Printf("[aigc] failed to persist card result for collection %d: %v", collectionID, err)
	}
}

func (h *AIGCHandler) markCardFailed(ctx context.Context, collectionID, userID uint, backgroundURL string) {
	updates := map[string]interface{}{
		"card_generation_status": models.PhysicalCollectionCardStatusFailed,
	}
	if backgroundURL != "" {
		updates["aigc_background_url"] = backgroundURL
	}
	if err := h.db.WithContext(ctx).
		Model(&models.PhysicalCollection{}).
		Where("id = ? AND user_id = ?", collectionID, userID).
		Updates(updates).Error; err != nil {
		log.Printf("[aigc] failed to mark card generation failed for collection %d: %v", collectionID, err)
	}
}

func (h *AIGCHandler) findUserCollection(id, userID uint) (*models.PhysicalCollection, error) {
	return h.findUserCollectionWithContext(context.Background(), id, userID)
}

func (h *AIGCHandler) findUserCollectionWithContext(ctx context.Context, id, userID uint) (*models.PhysicalCollection, error) {
	var collection models.PhysicalCollection
	if err := h.db.WithContext(ctx).Where("id = ? AND user_id = ?", id, userID).First(&collection).Error; err != nil {
		return nil, err
	}
	return &collection, nil
}

func buildCardMetadata(collection *models.PhysicalCollection) (services.CardMetadata, error) {
	attrs, err := services.ParseCollectibleAttributes(string(collection.Attributes))
	if err != nil {
		return services.CardMetadata{}, err
	}

	name := strings.TrimSpace(attrs.Series)
	if name == "" {
		name = strings.TrimSpace(attrs.IPName)
	}
	if name == "" {
		name = "Untitled Collectible"
	}

	rarity := deriveRarity(attrs)
	return services.CardMetadata{
		Name:     name,
		IP:       strings.TrimSpace(attrs.IPName),
		Rarity:   rarity,
		Material: strings.TrimSpace(attrs.Material),
	}, nil
}

func deriveRarity(attrs *services.CollectibleAttributes) string {
	condition := strings.ToLower(strings.TrimSpace(attrs.Condition))
	switch condition {
	case "mint", "pristine":
		return "Legendary"
	case "excellent", "near mint":
		return "Epic"
	case "good":
		return "Rare"
	default:
		return "Collector"
	}
}
