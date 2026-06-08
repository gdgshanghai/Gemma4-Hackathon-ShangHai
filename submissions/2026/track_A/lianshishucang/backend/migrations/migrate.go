package migrations

import (
	"github.com/lianshishucang/backend/models"
	"gorm.io/gorm"
)

func AutoMigrate(db *gorm.DB) error {
	return db.AutoMigrate(
		&models.User{},
		&models.NFTMetadata{},
		&models.PhysicalCollection{},

		&models.NFT{},
		&models.Listing{},
		&models.Offer{},
		&models.Transaction{},
		&models.Activity{},
	)
}
