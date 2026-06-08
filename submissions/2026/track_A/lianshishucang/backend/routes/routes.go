package routes

import (
	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/handlers"
	"github.com/lianshishucang/backend/middleware"
	"github.com/lianshishucang/backend/services"

	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

func RegisterRoutes(r *gin.Engine, db *gorm.DB, cfg *config.Config) {
	var blockchainService *services.BlockchainService
	if cfg.NFTContract != "" && cfg.Marketplace != "" {
		bc, err := services.NewBlockchainService(
			cfg.EthereumRPC,
			cfg.ChainID,
			"",
			"", "",
			cfg.NFTContract,
			cfg.Marketplace,
		)
		if err == nil {
			blockchainService = bc
		}
	}
	nftService := services.NewNFTService(db, cfg, blockchainService)
	marketplaceService := services.NewMarketplaceService(db, cfg, nftService)
	gemmaService := services.NewGemmaService(cfg)
	aigcService := services.NewAIGCService(db, cfg)
	compositingService := services.NewCompositingService(cfg)
	ipfsService := services.NewIPFSService(db, cfg)
	authHandler := handlers.NewAuthHandler(db, cfg)
	nftHandler := handlers.NewNFTHandler(db, cfg, nftService)
	marketplaceHandler := handlers.NewMarketplaceHandler(db, cfg, marketplaceService)
	collectionHandler := handlers.NewCollectionHandler(db, cfg, gemmaService)
	aigcHandler := handlers.NewAIGCHandler(db, cfg, aigcService, compositingService)
	web3Handler := handlers.NewWeb3Handler(db, cfg, ipfsService)

	public := r.Group("/api/v1")
	{
		public.GET("/auth/nonce/:address", authHandler.GetNonce)
		public.POST("/auth/login", authHandler.Login)
		public.GET("/users/:address", authHandler.GetUserByAddress)
		public.GET("/health", func(c *gin.Context) {
			c.JSON(200, gin.H{"status": "ok", "service": "链识数藏"})
		})

	}

	protected := r.Group("/api/v1")
	protected.Use(middleware.AuthMiddleware(cfg.JWTSecret))
	{
		protected.GET("/profile", authHandler.GetProfile)
		protected.PUT("/profile", authHandler.UpdateProfile)

		protected.POST("/nfts/metadata", nftHandler.RegisterMetadata)
		protected.GET("/nfts", nftHandler.ListNFTs)
		protected.GET("/nfts/:id", nftHandler.GetNFT)
		protected.GET("/nfts/my/owned", nftHandler.GetMyNFTs)
		protected.GET("/nfts/my/created", nftHandler.GetCreatedNFTs)

		protected.GET("/marketplace/listings", marketplaceHandler.ListListings)
		protected.GET("/marketplace/listings/:id", marketplaceHandler.GetListing)

		protected.POST("/collections/upload", collectionHandler.UploadAndIdentifyCollectible)
		protected.GET("/collections", collectionHandler.ListCollections)
		protected.GET("/collections/:id", collectionHandler.GetCollection)
		protected.PUT("/collections/:id", collectionHandler.UpdateCollection)
		protected.POST("/collections/:id/generate-card", aigcHandler.GenerateCard)
		protected.GET("/collections/:id/card-status", aigcHandler.GetCardStatus)
		protected.POST("/collections/:id/prepare-mint", web3Handler.PrepareMint)

	}
}
