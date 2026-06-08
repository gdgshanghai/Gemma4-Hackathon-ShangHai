package handlers

import (
	"context"
	"errors"
	"fmt"
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

type Web3Handler struct {
	db          *gorm.DB
	cfg         *config.Config
	ipfsService *services.IPFSService
}

func NewWeb3Handler(db *gorm.DB, cfg *config.Config, ipfsService *services.IPFSService) *Web3Handler {
	return &Web3Handler{db: db, cfg: cfg, ipfsService: ipfsService}
}

func (h *Web3Handler) PrepareMint(c *gin.Context) {
	userID := c.GetUint("user_id")
	collectionID, err := strconv.ParseUint(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid collection ID"})
		return
	}

	var collection models.PhysicalCollection
	if err := h.db.Where("id = ? AND user_id = ?", uint(collectionID), userID).First(&collection).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "collection not found"})
			return
		}
		log.Printf("[web3] failed to load collection %d: %v", collectionID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load collection"})
		return
	}

	if collection.Status == models.PhysicalCollectionStatusAwaitingMint && strings.TrimSpace(collection.TokenURI) != "" {
		c.JSON(http.StatusOK, gin.H{
			"tokenURI":        collection.TokenURI,
			"royaltyFee":      collection.RoyaltyFee,
			"contractAddress": h.cfg.NFTContract,
			"status":          collection.Status,
		})
		return
	}

	if collection.Status != models.PhysicalCollectionStatusStored {
		c.JSON(http.StatusBadRequest, gin.H{"error": "collection is not ready for mint preparation"})
		return
	}
	if collection.CardGenerationStatus != models.PhysicalCollectionCardStatusCompleted {
		c.JSON(http.StatusBadRequest, gin.H{"error": "virtual card is not ready"})
		return
	}
	if strings.TrimSpace(collection.VirtualCardURL) == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "virtual card URL is missing"})
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	tokenURI, err := h.ipfsService.UploadMetadataToIPFS(ctx, collection.ID)
	if err != nil {
		log.Printf("[web3] failed to upload metadata for collection %d: %v, using local fallback", collection.ID, err)
		tokenURI = fmt.Sprintf("http://localhost:8080/metadata/%d.json", collection.ID)
	}

	metaName, metaDescription, err := h.deriveMetadataValues(&collection)
	if err != nil {
		log.Printf("[web3] failed to derive metadata values for collection %d: %v", collection.ID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to derive metadata values"})
		return
	}

	royaltyFee := h.cfg.DefaultRoyaltyFee
	var metadata models.NFTMetadata
	err = h.db.Where("token_uri = ?", tokenURI).First(&metadata).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		metadata = models.NFTMetadata{
			UserID:      userID,
			TokenURI:    tokenURI,
			Name:        metaName,
			Description: metaDescription,
			Image:       collection.VirtualCardURL,
			RoyaltyFee:  royaltyFee,
		}
		if err := h.db.Create(&metadata).Error; err != nil {
			log.Printf("[web3] failed to create NFT metadata for collection %d: %v", collection.ID, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to persist NFT metadata"})
			return
		}
	} else if err != nil {
		log.Printf("[web3] failed to load NFT metadata for token URI %s: %v", tokenURI, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load NFT metadata"})
		return
	} else {
		updates := map[string]interface{}{
			"user_id":     userID,
			"name":        metaName,
			"description": metaDescription,
			"image":       collection.VirtualCardURL,
			"royalty_fee": royaltyFee,
		}
		if err := h.db.Model(&metadata).Updates(updates).Error; err != nil {
			log.Printf("[web3] failed to update NFT metadata %d: %v", metadata.ID, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update NFT metadata"})
			return
		}
	}

	updates := map[string]interface{}{
		"status":      models.PhysicalCollectionStatusAwaitingMint,
		"metadata_id": metadata.ID,
		"token_uri":   tokenURI,
		"royalty_fee": royaltyFee,
	}
	if err := h.db.Model(&models.PhysicalCollection{}).
		Where("id = ? AND user_id = ?", collection.ID, userID).
		Updates(updates).Error; err != nil {
		log.Printf("[web3] failed to update collection %d for mint prep: %v", collection.ID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update collection for mint prep"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"tokenURI":        tokenURI,
		"royaltyFee":      royaltyFee,
		"contractAddress": h.cfg.NFTContract,
		"status":          models.PhysicalCollectionStatusAwaitingMint,
	})
}

func (h *Web3Handler) deriveMetadataValues(collection *models.PhysicalCollection) (string, string, error) {
	attrs, err := services.ParseCollectibleAttributes(string(collection.Attributes))
	if err != nil {
		return "", "", err
	}

	name := strings.TrimSpace(attrs.Series)
	if name == "" {
		name = strings.TrimSpace(attrs.IPName)
	}
	if name == "" {
		name = fmt.Sprintf("Collection #%d", collection.ID)
	}

	descriptionParts := []string{"Physical collectible with AIGC virtual card."}
	if attrs.IPName != "" {
		descriptionParts = append(descriptionParts, "IP: "+attrs.IPName+".")
	}
	if attrs.Material != "" {
		descriptionParts = append(descriptionParts, "Material: "+attrs.Material+".")
	}
	if attrs.Condition != "" {
		descriptionParts = append(descriptionParts, "Condition: "+attrs.Condition+".")
	}

	return name, strings.Join(descriptionParts, " "), nil
}
