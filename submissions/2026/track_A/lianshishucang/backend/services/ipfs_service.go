package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"path/filepath"
	"strings"
	"time"

	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"gorm.io/gorm"
)

type IPFSService struct {
	db         *gorm.DB
	cfg        *config.Config
	httpClient *http.Client
}

var defaultIPFSService *IPFSService

type pinataUploadResponse struct {
	IpfsHash string `json:"IpfsHash"`
}

type erc721Metadata struct {
	Name        string                `json:"name"`
	Description string                `json:"description"`
	Image       string                `json:"image"`
	Attributes  []erc721MetadataTrait `json:"attributes"`
}

type erc721MetadataTrait struct {
	TraitType string `json:"trait_type"`
	Value     string `json:"value"`
}

func NewIPFSService(db *gorm.DB, cfg *config.Config) *IPFSService {
	service := &IPFSService{
		db:  db,
		cfg: cfg,
		httpClient: &http.Client{
			Timeout: 45 * time.Second,
		},
	}
	if defaultIPFSService == nil {
		defaultIPFSService = service
	}
	return service
}

func UploadMetadataToIPFS(collectionID uint) (string, error) {
	if defaultIPFSService == nil {
		return "", fmt.Errorf("IPFS service is not initialized")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	return defaultIPFSService.UploadMetadataToIPFS(ctx, collectionID)
}

func (s *IPFSService) UploadMetadataToIPFS(ctx context.Context, collectionID uint) (string, error) {
	if strings.TrimSpace(s.cfg.PinataAPIURL) == "" {
		return "", fmt.Errorf("PINATA_API_URL is not configured")
	}
	if strings.TrimSpace(s.cfg.PinataJWT) == "" {
		return "", fmt.Errorf("PINATA_JWT is not configured")
	}

	var collection models.PhysicalCollection
	if err := s.db.WithContext(ctx).First(&collection, collectionID).Error; err != nil {
		return "", err
	}
	if strings.TrimSpace(collection.VirtualCardURL) == "" {
		return "", fmt.Errorf("collection virtual card URL is empty")
	}

	metadata, err := s.buildMetadata(ctx, &collection)
	if err != nil {
		return "", err
	}
	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return "", fmt.Errorf("marshal ERC-721 metadata: %w", err)
	}

	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("file", filepath.Base(fmt.Sprintf("collection-%d-metadata.json", collectionID)))
	if err != nil {
		return "", fmt.Errorf("create multipart file: %w", err)
	}
	if _, err := part.Write(metadataJSON); err != nil {
		return "", fmt.Errorf("write metadata payload: %w", err)
	}
	if err := writer.Close(); err != nil {
		return "", fmt.Errorf("close multipart writer: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.cfg.PinataAPIURL, &body)
	if err != nil {
		return "", fmt.Errorf("build Pinata request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())
	req.Header.Set("Authorization", "Bearer "+s.cfg.PinataJWT)

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("Pinata request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return "", fmt.Errorf("read Pinata response: %w", err)
	}
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return "", fmt.Errorf("Pinata returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var parsed pinataUploadResponse
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return "", fmt.Errorf("invalid Pinata response: %w", err)
	}
	if strings.TrimSpace(parsed.IpfsHash) == "" {
		return "", fmt.Errorf("Pinata response missing IpfsHash")
	}

	return "ipfs://" + parsed.IpfsHash, nil
}

func (s *IPFSService) buildMetadata(ctx context.Context, collection *models.PhysicalCollection) (*erc721Metadata, error) {
	attrs, err := ParseCollectibleAttributes(string(collection.Attributes))
	if err != nil {
		return nil, fmt.Errorf("parse collection attributes: %w", err)
	}

	name := strings.TrimSpace(attrs.Series)
	if name == "" {
		name = strings.TrimSpace(attrs.IPName)
	}
	if name == "" {
		name = fmt.Sprintf("Collection #%d", collection.ID)
	}

	traits := []erc721MetadataTrait{}
	appendTrait := func(traitType, value string) {
		value = strings.TrimSpace(value)
		if value == "" {
			return
		}
		traits = append(traits, erc721MetadataTrait{TraitType: traitType, Value: value})
	}

	appendTrait("IP", attrs.IPName)
	appendTrait("Series", attrs.Series)
	appendTrait("Material", attrs.Material)
	appendTrait("Condition", attrs.Condition)
	appendTrait("Physical Location", collection.PhysicalLocation)
	for _, c := range attrs.DominantColors {
		appendTrait("Dominant Color", c)
	}
	for _, t := range attrs.StyleTags {
		appendTrait("Style Tag", t)
	}

	descriptionParts := []string{"Physical collectible with AIGC virtual card."}
	if attrs.IPName != "" {
		descriptionParts = append(descriptionParts, "IP: "+attrs.IPName+".")
	}
	if attrs.Material != "" {
		descriptionParts = append(descriptionParts, "Material: "+attrs.Material+".")
	}

	return &erc721Metadata{
		Name:        name,
		Description: strings.Join(descriptionParts, " "),
		Image:       strings.TrimSpace(collection.VirtualCardURL),
		Attributes:  traits,
	}, nil
}
