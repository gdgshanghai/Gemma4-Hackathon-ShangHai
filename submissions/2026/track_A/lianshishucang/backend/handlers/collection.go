package handlers

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"github.com/lianshishucang/backend/services"
	"gorm.io/gorm"
)

type CollectionHandler struct {
	db           *gorm.DB
	cfg          *config.Config
	gemmaService *services.GemmaService
}

type UpdateCollectionRequest struct {
	Attributes       *services.CollectibleAttributes `json:"attributes"`
	PhysicalLocation *string                         `json:"physical_location"`
}

func NewCollectionHandler(db *gorm.DB, cfg *config.Config, gemmaService *services.GemmaService) *CollectionHandler {
	return &CollectionHandler{db: db, cfg: cfg, gemmaService: gemmaService}
}

func (h *CollectionHandler) UploadAndIdentifyCollectible(c *gin.Context) {
	userID := c.GetUint("user_id")

	fileHeader, err := c.FormFile("image")
	if err != nil {
		fileHeader, err = c.FormFile("file")
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "image upload is required"})
			return
		}
	}

	if err := validateUploadFile(fileHeader); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	storedName, imagePath, err := h.saveUploadedFile(fileHeader)
	if err != nil {
		log.Printf("[collections] failed to save upload: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to save uploaded file"})
		return
	}

	rawImageURL := strings.TrimRight(h.cfg.UploadBaseURL, "/") + "/" + storedName
	collection := &models.PhysicalCollection{
		UserID:               userID,
		Name:                 "",
		RawImageURL:          rawImageURL,
		Status:               models.PhysicalCollectionStatusPendingAI,
		CardGenerationStatus: models.PhysicalCollectionCardStatusPending,
	}

	if err := h.db.Create(collection).Error; err != nil {
		log.Printf("[collections] failed to create record: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create collection"})
		return
	}

	go h.analyzeCollection(collection.ID, userID, imagePath)

	c.JSON(http.StatusAccepted, gin.H{
		"code":          http.StatusAccepted,
		"message":       "Image uploaded, AI identification started",
		"collection_id": collection.ID,
	})
}

func (h *CollectionHandler) UploadCollection(c *gin.Context) {
	h.UploadAndIdentifyCollectible(c)
}

func (h *CollectionHandler) ListCollections(c *gin.Context) {
	userID := c.GetUint("user_id")

	var collections []models.PhysicalCollection
	if err := h.db.Where("user_id = ?", userID).
		Order("created_at DESC").
		Find(&collections).Error; err != nil {
		log.Printf("[collections] failed to list collections: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch collections"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"collections": collections})
}

func (h *CollectionHandler) GetCollection(c *gin.Context) {
	userID := c.GetUint("user_id")
	id, err := strconv.ParseUint(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid collection ID"})
		return
	}

	collection, err := h.findUserCollection(uint(id), userID)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			c.JSON(http.StatusNotFound, gin.H{"error": "collection not found"})
			return
		}
		log.Printf("[collections] failed to load collection: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch collection"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":            collection.ID,
		"user_id":       collection.UserID,
		"name":          collection.Name,
		"raw_image_url": collection.RawImageURL,
		"aigc_status":   collection.Status,
		"attributes":    collection.Attributes,
		"created_at":    collection.CreatedAt,
		"updated_at":    collection.UpdatedAt,
	})
}

func (h *CollectionHandler) UpdateCollection(c *gin.Context) {
	userID := c.GetUint("user_id")
	id, err := strconv.ParseUint(c.Param("id"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid collection ID"})
		return
	}

	var req UpdateCollectionRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Attributes == nil && req.PhysicalLocation == nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "no updatable fields provided"})
		return
	}

	updates := make(map[string]interface{})
	if req.Attributes != nil {
		normalized, err := services.NormalizeCollectibleAttributes(*req.Attributes)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		body, err := json.Marshal(normalized)
		if err != nil {
			log.Printf("[collections] failed to marshal attributes: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to serialize attributes"})
			return
		}
		updates["attributes"] = json.RawMessage(body)
	}
	if req.PhysicalLocation != nil {
		updates["physical_location"] = strings.TrimSpace(*req.PhysicalLocation)
	}

	result := h.db.Model(&models.PhysicalCollection{}).
		Where("id = ? AND user_id = ?", uint(id), userID).
		Updates(updates)
	if result.Error != nil {
		log.Printf("[collections] failed to update collection: %v", result.Error)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update collection"})
		return
	}
	if result.RowsAffected == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "collection not found"})
		return
	}

	updated, err := h.findUserCollection(uint(id), userID)
	if err != nil {
		log.Printf("[collections] failed to reload collection: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch updated collection"})
		return
	}

	c.JSON(http.StatusOK, updated)
}

func (h *CollectionHandler) analyzeCollection(collectionID, userID uint, imagePath string) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	imageName := filepath.Base(imagePath)
	identified, err := h.gemmaService.AnalyzeCollectibleImage(ctx, imagePath)
	if err != nil {
		log.Printf("[ai] collection=%d image=%s provider=all result=failed error=%q using_defaults=true", collectionID, imageName, err)
		identified = defaultCollectibleAttributes()
	}

	body, err := json.Marshal(identified)
	if err != nil {
		log.Printf("[collections] failed to marshal Gemma response for collection %d: %v", collectionID, err)
		if updateErr := h.db.WithContext(ctx).
			Model(&models.PhysicalCollection{}).
			Where("id = ? AND user_id = ?", collectionID, userID).
			Update("status", models.PhysicalCollectionStatusFailed).Error; updateErr != nil {
			log.Printf("[collections] failed to mark collection %d as failed: %v", collectionID, updateErr)
		}
		return
	}

	log.Printf("[ai] collection=%d image=%s result=%s", collectionID, imageName, string(body))

	updates := map[string]interface{}{
		"name":       strings.TrimSpace(identified.Title),
		"attributes": json.RawMessage(body),
		"status":     models.PhysicalCollectionStatusStored,
	}
	if err := h.db.WithContext(ctx).
		Model(&models.PhysicalCollection{}).
		Where("id = ? AND user_id = ?", collectionID, userID).
		Updates(updates).Error; err != nil {
		log.Printf("[collections] failed to persist AI attributes for collection %d: %v", collectionID, err)
	}
}

func defaultCollectibleAttributes() *services.GemmaResponse {
	return &services.GemmaResponse{
		Title:        "Unidentified Collectible",
		SeriesArtist: "Unknown Artist",
		Material:     "Unknown",
		Dimensions:   "Standard",
		MarketValue:  "TBD",
		StyleTags:    []string{"collectible"},
	}
}

func (h *CollectionHandler) saveUploadedFile(fileHeader *multipart.FileHeader) (string, string, error) {
	if err := os.MkdirAll(h.cfg.UploadDir, 0o755); err != nil {
		return "", "", fmt.Errorf("create upload dir: %w", err)
	}

	ext := strings.ToLower(filepath.Ext(fileHeader.Filename))
	nameBytes := make([]byte, 16)
	if _, err := rand.Read(nameBytes); err != nil {
		return "", "", fmt.Errorf("generate upload filename: %w", err)
	}
	storedName := hex.EncodeToString(nameBytes) + ext
	destination := filepath.Join(h.cfg.UploadDir, storedName)

	if err := saveMultipartFile(fileHeader, destination); err != nil {
		return "", "", err
	}
	return storedName, destination, nil
}

func saveMultipartFile(fileHeader *multipart.FileHeader, destination string) error {
	src, err := fileHeader.Open()
	if err != nil {
		return err
	}
	defer src.Close()

	dst, err := os.Create(destination)
	if err != nil {
		return err
	}
	defer dst.Close()

	_, err = dst.ReadFrom(src)
	return err
}

func validateUploadFile(fileHeader *multipart.FileHeader) error {
	if fileHeader.Size == 0 {
		return fmt.Errorf("uploaded file is empty")
	}

	ext := strings.ToLower(filepath.Ext(fileHeader.Filename))
	switch ext {
	case ".jpg", ".jpeg", ".png", ".webp":
		return nil
	default:
		return fmt.Errorf("unsupported file type")
	}
}

func (h *CollectionHandler) findUserCollection(id, userID uint) (*models.PhysicalCollection, error) {
	var collection models.PhysicalCollection
	if err := h.db.Where("id = ? AND user_id = ?", id, userID).First(&collection).Error; err != nil {
		return nil, err
	}
	return &collection, nil
}
