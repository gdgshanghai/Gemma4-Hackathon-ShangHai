package services

import (
	"context"
	"log"
	"math/big"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/ethereum/go-ethereum"
	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/ethclient"
	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/models"
	"gorm.io/gorm"
)

type EventListener struct {
	client *ethclient.Client
	db     *gorm.DB
	cfg    *config.Config

	nftAddr         common.Address
	marketplaceAddr common.Address

	eventTopics map[string]common.Hash
	eventArgs   map[string]abi.Arguments

	lastBlock uint64
	mu        sync.Mutex

	pollInterval time.Duration
	startBlock   uint64
}

func NewEventListener(cfg *config.Config, db *gorm.DB) (*EventListener, error) {
	client, err := ethclient.Dial(cfg.EthereumRPC)
	if err != nil {
		return nil, err
	}

	el := &EventListener{
		client:          client,
		db:              db,
		cfg:             cfg,
		nftAddr:         common.HexToAddress(cfg.NFTContract),
		marketplaceAddr: common.HexToAddress(cfg.Marketplace),
		eventTopics:     make(map[string]common.Hash),
		eventArgs:       make(map[string]abi.Arguments),
		pollInterval:    5 * time.Second,
		startBlock:      0,
	}

	el.registerEvent("NFTMinted",
		"NFTMinted(uint256,address,address,string,uint96,uint256)",
		[]string{"string uri", "uint96 royaltyFee", "uint256 createdAt"},
	)
	el.registerEvent("ListingCreated",
		"ListingCreated(uint256,uint256,address,address,uint256)",
		[]string{"address seller", "uint256 price"},
	)
	el.registerEvent("ListingCancelled",
		"ListingCancelled(uint256)",
		nil,
	)
	el.registerEvent("ItemSold",
		"ItemSold(uint256,uint256,address,address,address,uint256,uint256,uint256)",
		[]string{"address seller", "address buyer", "uint256 price", "uint256 platformFee", "uint256 creatorRoyalty"},
	)
	el.registerEvent("OfferCreated",
		"OfferCreated(uint256,uint256,address,address,uint256,uint256)",
		[]string{"address bidder", "uint256 price", "uint256 expiration"},
	)
	el.registerEvent("OfferCancelled",
		"OfferCancelled(uint256)",
		nil,
	)
	el.registerEvent("OfferAccepted",
		"OfferAccepted(uint256,uint256,address,address,address,uint256)",
		[]string{"address seller", "address bidder", "uint256 price"},
	)

	return el, nil
}

func mustABIType(t string) abi.Type {
	typ, err := abi.NewType(t, "", nil)
	if err != nil {
		panic(err)
	}
	return typ
}

func (l *EventListener) registerEvent(name, sig string, args []string) {
	l.eventTopics[name] = crypto.Keccak256Hash([]byte(sig))
	if len(args) > 0 {
		components := make(abi.Arguments, len(args))
		for i, a := range args {
			parts := strings.SplitN(a, " ", 2)
			components[i] = abi.Argument{Name: parts[1], Type: mustABIType(parts[0])}
		}
		l.eventArgs[name] = components
	}
}

func (l *EventListener) Start(ctx context.Context) {
	header, err := l.client.HeaderByNumber(ctx, nil)
	if err != nil {
		log.Printf("[event_listener] failed to get latest block: %v", err)
		return
	}
	l.lastBlock = header.Number.Uint64()
	log.Printf("[event_listener] starting from block %d", l.lastBlock)

	ticker := time.NewTicker(l.pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("[event_listener] stopped")
			return
		case <-ticker.C:
			l.poll(ctx)
		}
	}
}

func (l *EventListener) poll(ctx context.Context) {
	header, err := l.client.HeaderByNumber(ctx, nil)
	if err != nil {
		log.Printf("[event_listener] header error: %v", err)
		return
	}
	toBlock := header.Number.Uint64()
	if toBlock <= l.lastBlock {
		return
	}

	l.processRange(ctx, l.lastBlock+1, toBlock)
	l.mu.Lock()
	l.lastBlock = toBlock
	l.mu.Unlock()
}

func (l *EventListener) processRange(ctx context.Context, from, to uint64) {
	if l.cfg.NFTContract != "" {
		l.processContractEvents(ctx, l.nftAddr, from, to, map[string]string{
			"NFTMinted": "NFTMinted",
		})
	}
	if l.cfg.Marketplace != "" {
		l.processContractEvents(ctx, l.marketplaceAddr, from, to, map[string]string{
			"ListingCreated":   "ListingCreated",
			"ListingCancelled": "ListingCancelled",
			"ItemSold":         "ItemSold",
			"OfferCreated":     "OfferCreated",
			"OfferCancelled":   "OfferCancelled",
			"OfferAccepted":    "OfferAccepted",
		})
	}
}

func (l *EventListener) processContractEvents(ctx context.Context, addr common.Address, from, to uint64, eventNames map[string]string) {
	topics := make([]common.Hash, 0, len(eventNames))
	for _, name := range eventNames {
		topics = append(topics, l.eventTopics[name])
	}

	query := ethereum.FilterQuery{
		Addresses: []common.Address{addr},
		FromBlock: new(big.Int).SetUint64(from),
		ToBlock:   new(big.Int).SetUint64(to),
		Topics:    [][]common.Hash{topics},
	}

	logs, err := l.client.FilterLogs(ctx, query)
	if err != nil {
		log.Printf("[event_listener] FilterLogs error for %s: %v", addr.Hex(), err)
		return
	}

	for _, vLog := range logs {
		l.handleLog(addr, vLog)
	}
}

func (l *EventListener) handleLog(addr common.Address, vLog types.Log) {
	if len(vLog.Topics) == 0 {
		return
	}
	sig := vLog.Topics[0]

	for name, topic := range l.eventTopics {
		if topic != sig {
			continue
		}

		switch name {
		case "NFTMinted":
			l.handleNFTMinted(vLog)
		case "ListingCreated":
			l.handleListingCreated(vLog)
		case "ListingCancelled":
			l.handleListingCancelled(vLog)
		case "ItemSold":
			l.handleItemSold(vLog)
		}
		return
	}
}

func (l *EventListener) findOrCreateUser(addr common.Address) (*models.User, error) {
	addrStr := strings.ToLower(addr.Hex())
	var user models.User
	err := l.db.Where("wallet_address = ?", addrStr).First(&user).Error
	if err == nil {
		return &user, nil
	}
	user = models.User{WalletAddress: addrStr}
	if err := l.db.Create(&user).Error; err != nil {
		return nil, err
	}
	return &user, nil
}

func (l *EventListener) unpackEvent(name string, data []byte) (map[string]interface{}, error) {
	args, ok := l.eventArgs[name]
	if !ok || args == nil {
		return nil, nil
	}
	vals, err := args.Unpack(data)
	if err != nil {
		return nil, err
	}
	result := make(map[string]interface{})
	for i, arg := range args {
		result[arg.Name] = vals[i]
	}
	return result, nil
}

func (l *EventListener) handleNFTMinted(vLog types.Log) {
	data, _ := l.unpackEvent("NFTMinted", vLog.Data)
	tokenID := vLog.Topics[1].Big().Uint64()
	creator := common.BytesToAddress(vLog.Topics[2].Bytes())
	owner := common.BytesToAddress(vLog.Topics[3].Bytes())

	var uri string
	var royaltyFee uint64
	if data != nil {
		uri, _ = data["uri"].(string)
		royaltyFee, _ = data["royaltyFee"].(uint64)
	}

	creatorUser, err := l.findOrCreateUser(creator)
	if err != nil {
		log.Printf("[event_listener] findOrCreateUser creator error: %v", err)
		return
	}
	ownerUser, err := l.findOrCreateUser(owner)
	if err != nil {
		log.Printf("[event_listener] findOrCreateUser owner error: %v", err)
		return
	}

	var existing models.NFT
	result := l.db.Where("token_id = ? AND contract_address = ?", tokenID, l.cfg.NFTContract).First(&existing)
	if result.Error == nil {
		return
	}

	var meta models.NFTMetadata
	if uri != "" {
		l.db.Where("token_uri = ?", uri).First(&meta)
	}

	nft := models.NFT{
		TokenID:         tokenID,
		ContractAddress: l.cfg.NFTContract,
		OwnerID:         ownerUser.ID,
		CreatorID:       creatorUser.ID,
		TokenURI:        uri,
		Metadata:        uri,
		Name:            meta.Name,
		Description:     meta.Description,
		Image:           meta.Image,
		RoyaltyFee:      royaltyFee,
		TxHash:          vLog.TxHash.Hex(),
		Status:          "active",
	}
	if err := l.db.Create(&nft).Error; err != nil {
		log.Printf("[event_listener] create NFT error: %v", err)
		return
	}
	if uri != "" {
		updates := map[string]interface{}{
			"nft_id":    nft.ID,
			"status":    models.PhysicalCollectionStatusMinted,
			"token_uri": uri,
		}
		if meta.ID != 0 {
			updates["metadata_id"] = meta.ID
		}
		if err := l.db.Model(&models.PhysicalCollection{}).
			Where("token_uri = ? OR metadata_id = ?", uri, meta.ID).
			Updates(updates).Error; err != nil {
			log.Printf("[event_listener] update PhysicalCollection after mint error: %v", err)
		}
	}
	log.Printf("[event_listener] NFTMinted: tokenID=%d tx=%s", tokenID, vLog.TxHash.Hex())
	l.logActivity(&nft.ID, creatorUser.ID, "mint", "tokenID: "+strconv.FormatUint(tokenID, 10), vLog.TxHash.Hex())
}

func (l *EventListener) handleListingCreated(vLog types.Log) {
	data, _ := l.unpackEvent("ListingCreated", vLog.Data)
	listingID := vLog.Topics[1].Big().Uint64()
	tokenID := vLog.Topics[2].Big().Uint64()

	var sellerAddr common.Address
	var price string
	if data != nil {
		sellerAddr, _ = data["seller"].(common.Address)
		if p, ok := data["price"].(*big.Int); ok {
			price = p.String()
		}
	}

	seller, err := l.findOrCreateUser(sellerAddr)
	if err != nil {
		return
	}

	var nft models.NFT
	if err := l.db.Where("token_id = ? AND contract_address = ?", tokenID, l.cfg.NFTContract).First(&nft).Error; err != nil {
		return
	}

	listing := models.Listing{
		NFTID:     nft.ID,
		SellerID:  seller.ID,
		ListingID: listingID,
		PriceWei:  price,
		Status:    "active",
		TxHash:    vLog.TxHash.Hex(),
	}
	if err := l.db.Create(&listing).Error; err != nil {
		log.Printf("[event_listener] create listing error: %v", err)
		return
	}
	log.Printf("[event_listener] ListingCreated: listingID=%d tokenID=%d", listingID, tokenID)
	l.logActivity(&nft.ID, seller.ID, "listing_created", "price: "+price+" wei", vLog.TxHash.Hex())
}

func (l *EventListener) handleListingCancelled(vLog types.Log) {
	listingID := vLog.Topics[1].Big().Uint64()
	l.db.Model(&models.Listing{}).Where("listing_id = ?", listingID).Update("status", "cancelled")
	log.Printf("[event_listener] ListingCancelled: listingID=%d", listingID)
}

func (l *EventListener) handleItemSold(vLog types.Log) {
	data, _ := l.unpackEvent("ItemSold", vLog.Data)
	listingID := vLog.Topics[1].Big().Uint64()
	tokenID := vLog.Topics[2].Big().Uint64()

	var buyerAddr common.Address
	var price string
	if data != nil {
		buyerAddr, _ = data["buyer"].(common.Address)
		if p, ok := data["price"].(*big.Int); ok {
			price = p.String()
		}
	}

	buyer, err := l.findOrCreateUser(buyerAddr)
	if err != nil {
		log.Printf("[event_listener] findOrCreateUser buyer error: %v", err)
		return
	}

	var nft models.NFT
	if err := l.db.Where("token_id = ? AND contract_address = ?", tokenID, l.cfg.NFTContract).First(&nft).Error; err != nil {
		return
	}

	err = l.db.Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&models.Listing{}).Where("listing_id = ?", listingID).Update("status", "sold").Error; err != nil {
			return err
		}
		if err := tx.Model(&models.NFT{}).Where("id = ?", nft.ID).Update("owner_id", buyer.ID).Error; err != nil {
			return err
		}
		if err := tx.Model(&models.PhysicalCollection{}).Where("nft_id = ?", nft.ID).Updates(map[string]interface{}{
			"user_id": buyer.ID,
		}).Error; err != nil {
			return err
		}
		txLog := &models.Transaction{
			TxHash: vLog.TxHash.Hex(),
			FromID: nft.OwnerID,
			ToID:   buyer.ID,
			NFTID:  &nft.ID,
			Type:   "purchase",
			Amount: price,
			Status: "confirmed",
		}
		return tx.Create(txLog).Error
	})
	if err != nil {
		log.Printf("[event_listener] ItemSold transaction error: %v", err)
		return
	}
	log.Printf("[event_listener] ItemSold: listingID=%d tokenID=%d buyer=%s", listingID, tokenID, buyerAddr.Hex())
	l.logActivity(&nft.ID, buyer.ID, "purchase", "price: "+price+" wei", vLog.TxHash.Hex())
}

func (l *EventListener) logActivity(nftID *uint, userID uint, action, detail, txHash string) {
	l.db.Create(&models.Activity{
		NFTID:  nftID,
		UserID: userID,
		Action: action,
		Detail: detail,
		TxHash: txHash,
	})
}
