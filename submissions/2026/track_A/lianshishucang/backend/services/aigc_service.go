package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"gorm.io/gorm"
)

type AIGCService struct {
	db         *gorm.DB
	cfg        *config.Config
	httpClient *http.Client
}

type aigcGenerateRequest struct {
	Model    string `json:"model,omitempty"`
	Prompt   string `json:"prompt"`
	ImageURL string `json:"image_url"`
}

type aigcGenerateResponse struct {
	ImageURL string `json:"image_url"`
}

var defaultAIGCService *AIGCService

func NewAIGCService(db *gorm.DB, cfg *config.Config) *AIGCService {
	service := &AIGCService{
		db:  db,
		cfg: cfg,
		httpClient: &http.Client{
			Timeout: 45 * time.Second,
		},
	}
	if defaultAIGCService == nil {
		defaultAIGCService = service
	}
	return service
}

func GenerateStylizedBackground(collectionID uint, stylePrompt string) (string, error) {
	if defaultAIGCService == nil {
		return "", fmt.Errorf("AIGC service is not initialized")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	return defaultAIGCService.GenerateStylizedBackground(ctx, collectionID, stylePrompt)
}

func (s *AIGCService) GenerateStylizedBackground(ctx context.Context, collectionID uint, stylePrompt string) (string, error) {
	if s.db == nil {
		return "", fmt.Errorf("database is not configured for AIGC service")
	}
	if strings.TrimSpace(s.cfg.AIGCAPIURL) == "" {
		return "", fmt.Errorf("AIGC_API_URL is not configured")
	}

	var collection models.PhysicalCollection
	if err := s.db.WithContext(ctx).First(&collection, collectionID).Error; err != nil {
		return "", err
	}
	if strings.TrimSpace(collection.RawImageURL) == "" {
		return "", fmt.Errorf("collection raw image URL is empty")
	}
	if len(collection.Attributes) == 0 {
		return "", fmt.Errorf("collection attributes are empty")
	}

	attrs, err := ParseCollectibleAttributes(string(collection.Attributes))
	if err != nil {
		return "", fmt.Errorf("parse collection attributes: %w", err)
	}

	prompt := buildAIGCPrompt(stylePrompt, attrs)
	requestBody, err := json.Marshal(aigcGenerateRequest{
		Model:    s.cfg.AIGCModel,
		Prompt:   prompt,
		ImageURL: collection.RawImageURL,
	})
	if err != nil {
		return "", fmt.Errorf("marshal AIGC request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.cfg.AIGCAPIURL, bytes.NewReader(requestBody))
	if err != nil {
		return "", fmt.Errorf("build AIGC request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if strings.TrimSpace(s.cfg.AIGCAPIKey) != "" {
		req.Header.Set("Authorization", "Bearer "+s.cfg.AIGCAPIKey)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		log.Printf("[aigc] request failed: %v", err)
		return "", fmt.Errorf("AIGC request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return "", fmt.Errorf("read AIGC response: %w", err)
	}
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		log.Printf("[aigc] non-2xx response status=%d body=%s", resp.StatusCode, string(respBody))
		return "", fmt.Errorf("AIGC API returned status %d", resp.StatusCode)
	}

	var parsed aigcGenerateResponse
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		log.Printf("[aigc] invalid response envelope: %v body=%s", err, string(respBody))
		return "", fmt.Errorf("invalid AIGC response JSON: %w", err)
	}
	if strings.TrimSpace(parsed.ImageURL) == "" {
		return "", fmt.Errorf("AIGC response missing image_url")
	}

	return parsed.ImageURL, nil
}

func buildAIGCPrompt(stylePrompt string, attrs *CollectibleAttributes) string {
	parts := []string{
		strings.TrimSpace(stylePrompt),
		"stylized trading card background",
	}
	if attrs != nil {
		if attrs.IPName != "" {
			parts = append(parts, "IP: "+attrs.IPName)
		}
		if attrs.Series != "" {
			parts = append(parts, "Series: "+attrs.Series)
		}
		if attrs.Material != "" {
			parts = append(parts, "Material: "+attrs.Material)
		}
		if len(attrs.StyleTags) > 0 {
			parts = append(parts, "Style tags: "+strings.Join(attrs.StyleTags, ", "))
		}
		if len(attrs.DominantColors) > 0 {
			parts = append(parts, "Dominant colors: "+strings.Join(attrs.DominantColors, ", "))
		}
	}
	return strings.Join(parts, ". ")
}
