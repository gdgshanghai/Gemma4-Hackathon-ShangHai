package services

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"image"
	"image/color"
	_ "image/jpeg"
	_ "image/png"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/fogleman/gg"
	"github.com/lianshishucang/backend/config"
)

type CardMetadata struct {
	Name     string
	IP       string
	Rarity   string
	Material string
}

type CompositingService struct {
	cfg        *config.Config
	httpClient *http.Client
}

var defaultCompositingService *CompositingService

func NewCompositingService(cfg *config.Config) *CompositingService {
	service := &CompositingService{
		cfg: cfg,
		httpClient: &http.Client{
			Timeout: 45 * time.Second,
		},
	}
	if defaultCompositingService == nil {
		defaultCompositingService = service
	}
	return service
}

func RenderVirtualCard(backgroundURL string, itemImageURL string, metadata CardMetadata) (string, error) {
	if defaultCompositingService == nil {
		return "", fmt.Errorf("compositing service is not initialized")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	return defaultCompositingService.RenderVirtualCard(ctx, backgroundURL, itemImageURL, metadata)
}

func (s *CompositingService) RenderVirtualCard(ctx context.Context, backgroundURL string, itemImageURL string, metadata CardMetadata) (string, error) {
	background, err := s.downloadImage(ctx, backgroundURL)
	if err != nil {
		return "", fmt.Errorf("download background image: %w", err)
	}
	item, err := s.downloadImage(ctx, itemImageURL)
	if err != nil {
		return "", fmt.Errorf("download collectible image: %w", err)
	}

	const cardWidth = 800
	const cardHeight = 1200

	dc := gg.NewContext(cardWidth, cardHeight)
	s.drawScaledBackground(dc, background, cardWidth, cardHeight)
	s.drawCenteredItem(dc, item, cardWidth, cardHeight)
	s.drawTextOverlay(dc, cardWidth, cardHeight)

	if err := dc.LoadFontFace(s.cfg.CardFontPath, 46); err != nil {
		return "", fmt.Errorf("load title font %q: %w", s.cfg.CardFontPath, err)
	}
	dc.SetColor(color.White)
	dc.DrawStringAnchored(strings.TrimSpace(metadata.Name), 60, 930, 0, 0.5)

	if err := dc.LoadFontFace(s.cfg.CardFontPath, 28); err != nil {
		return "", fmt.Errorf("load body font %q: %w", s.cfg.CardFontPath, err)
	}
	dc.SetRGBA255(235, 240, 255, 230)
	dc.DrawStringAnchored("IP: "+strings.TrimSpace(metadata.IP), 60, 1000, 0, 0.5)
	dc.DrawStringAnchored("Material: "+strings.TrimSpace(metadata.Material), 60, 1045, 0, 0.5)
	dc.DrawStringAnchored("Rarity: "+strings.TrimSpace(metadata.Rarity), 60, 1090, 0, 0.5)

	if err := os.MkdirAll(s.cfg.CardOutputDir, 0o755); err != nil {
		return "", fmt.Errorf("create card output dir: %w", err)
	}
	filename, err := randomPNGName()
	if err != nil {
		return "", err
	}
	outputPath := filepath.Join(s.cfg.CardOutputDir, filename)
	if err := dc.SavePNG(outputPath); err != nil {
		return "", fmt.Errorf("save virtual card png: %w", err)
	}

	return strings.TrimRight(s.cfg.CardBaseURL, "/") + "/" + filename, nil
}

func (s *CompositingService) downloadImage(ctx context.Context, imageURL string) (image.Image, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, imageURL, nil)
	if err != nil {
		return nil, err
	}
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, fmt.Errorf("image request returned status %d", resp.StatusCode)
	}
	img, _, err := image.Decode(resp.Body)
	if err != nil {
		return nil, err
	}
	return img, nil
}

func (s *CompositingService) drawScaledBackground(dc *gg.Context, img image.Image, cardWidth, cardHeight int) {
	bounds := img.Bounds()
	scaleX := float64(cardWidth) / float64(bounds.Dx())
	scaleY := float64(cardHeight) / float64(bounds.Dy())
	scale := scaleX
	if scaleY > scale {
		scale = scaleY
	}
	width := float64(bounds.Dx()) * scale
	height := float64(bounds.Dy()) * scale
	x := (float64(cardWidth) - width) / 2
	y := (float64(cardHeight) - height) / 2

	dc.Push()
	dc.Translate(x, y)
	dc.Scale(scale, scale)
	dc.DrawImage(img, 0, 0)
	dc.Pop()
}

func (s *CompositingService) drawCenteredItem(dc *gg.Context, img image.Image, cardWidth, cardHeight int) {
	bounds := img.Bounds()
	maxWidth := float64(cardWidth) * 0.7
	maxHeight := float64(cardHeight) * 0.52
	scaleX := maxWidth / float64(bounds.Dx())
	scaleY := maxHeight / float64(bounds.Dy())
	scale := scaleX
	if scaleY < scale {
		scale = scaleY
	}
	if scale > 1 {
		scale = 1
	}

	width := float64(bounds.Dx()) * scale
	height := float64(bounds.Dy()) * scale
	x := (float64(cardWidth) - width) / 2
	y := float64(cardHeight)*0.18 + (maxHeight-height)/2

	dc.Push()
	dc.Translate(x, y)
	dc.Scale(scale, scale)
	dc.DrawImage(img, 0, 0)
	dc.Pop()
}

func (s *CompositingService) drawTextOverlay(dc *gg.Context, cardWidth, cardHeight int) {
	overlayY := float64(cardHeight) * 0.72
	overlayHeight := float64(cardHeight) * 0.22
	dc.SetRGBA255(20, 24, 36, 185)
	dc.DrawRoundedRectangle(32, overlayY, float64(cardWidth)-64, overlayHeight, 28)
	dc.Fill()
	dc.SetRGBA255(255, 255, 255, 60)
	dc.SetLineWidth(2)
	dc.DrawRoundedRectangle(32, overlayY, float64(cardWidth)-64, overlayHeight, 28)
	dc.Stroke()
}

func randomPNGName() (string, error) {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return "", fmt.Errorf("generate card filename: %w", err)
	}
	return hex.EncodeToString(buf) + ".png", nil
}
