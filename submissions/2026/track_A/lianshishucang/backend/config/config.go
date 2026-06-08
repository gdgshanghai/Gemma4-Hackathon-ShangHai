package config

import (
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	ServerPort        string
	DatabaseURL       string
	JWTSecret         string
	EthereumRPC       string
	ChainID           int64
	NFTContract       string
	Marketplace       string
	PlatformFeeBps    uint64
	FeeRecipient      string
	GemmaAPIURL       string
	GemmaAPIKey       string
	GemmaModel        string
	AIGCAPIURL        string
	AIGCAPIKey        string
	AIGCModel         string
	PinataAPIURL      string
	PinataJWT         string
	DefaultRoyaltyFee uint64
	UploadBaseURL     string
	UploadDir         string
	CardOutputDir     string
	CardBaseURL       string
	CardFontPath      string
}

func Load() *Config {
	godotenv.Load()

	return &Config{
		ServerPort:        getEnv("SERVER_PORT", "8080"),
		DatabaseURL:       getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/lianshishucang?sslmode=disable"),
		JWTSecret:         getEnv("JWT_SECRET", "change-me-in-production"),
		EthereumRPC:       getEnv("ETHEREUM_RPC", "https://eth-sepolia.g.alchemy.com/v2/demo"),
		ChainID:           getEnvInt("CHAIN_ID", 11155111),
		NFTContract:       getEnv("NFT_CONTRACT", ""),
		Marketplace:       getEnv("MARKETPLACE_CONTRACT", ""),
		PlatformFeeBps:    getEnvUint("PLATFORM_FEE_BPS", 250),
		FeeRecipient:      getEnv("FEE_RECIPIENT", "0x0000000000000000000000000000000000000000"),
		GemmaAPIURL:       getEnv("GEMMA_API_URL", ""),
		GemmaAPIKey:       getEnv("GEMMA_API_KEY", ""),
		GemmaModel:        getEnv("GEMMA_MODEL", "gemma-4-multimodal"),
		AIGCAPIURL:        getEnv("AIGC_API_URL", ""),
		AIGCAPIKey:        getEnv("AIGC_API_KEY", ""),
		AIGCModel:         getEnv("AIGC_MODEL", "stable-diffusion-img2img"),
		PinataAPIURL:      getEnv("PINATA_API_URL", "https://api.pinata.cloud/pinning/pinFileToIPFS"),
		PinataJWT:         getEnv("PINATA_JWT", ""),
		DefaultRoyaltyFee: getEnvUint("DEFAULT_ROYALTY_FEE", 250),
		UploadBaseURL:     getEnv("UPLOAD_BASE_URL", "http://localhost:8080/uploads"),
		UploadDir:         getEnv("UPLOAD_DIR", "storage/uploads"),
		CardOutputDir:     getEnv("CARD_OUTPUT_DIR", "tmp/cards"),
		CardBaseURL:       getEnv("CARD_BASE_URL", "http://localhost:8080/cards"),
		CardFontPath:      getEnv("CARD_FONT_PATH", "fonts/Roboto-Bold.ttf"),
	}
}

func getEnv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

func getEnvInt(key string, fallback int64) int64 {
	if val := os.Getenv(key); val != "" {
		if n, err := strconv.ParseInt(val, 10, 64); err == nil {
			return n
		}
	}
	return fallback
}

func getEnvUint(key string, fallback uint64) uint64 {
	if val := os.Getenv(key); val != "" {
		if n, err := strconv.ParseUint(val, 10, 64); err == nil {
			return n
		}
	}
	return fallback
}
