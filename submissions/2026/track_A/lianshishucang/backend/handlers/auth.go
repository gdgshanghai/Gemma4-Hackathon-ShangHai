package handlers

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strings"
	"time"

	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/lianshishucang/backend/config"
	"github.com/lianshishucang/backend/middleware"
	"github.com/lianshishucang/backend/models"
	"gorm.io/gorm"
)

type AuthHandler struct {
	db  *gorm.DB
	cfg *config.Config
}

func NewAuthHandler(db *gorm.DB, cfg *config.Config) *AuthHandler {
	return &AuthHandler{db: db, cfg: cfg}
}

type NonceResponse struct {
	Nonce      string `json:"nonce"`
	WalletAddr string `json:"wallet_address"`
	Message    string `json:"message"`
}

type LoginRequest struct {
	WalletAddress string `json:"wallet_address" binding:"required"`
	Signature     string `json:"signature" binding:"required"`
	Message       string `json:"message" binding:"required"`
}

type LoginResponse struct {
	Token    string `json:"token"`
	UserID   uint   `json:"user_id"`
	Nickname string `json:"nickname"`
}

func (h *AuthHandler) GetNonce(c *gin.Context) {
	walletAddr := c.Param("address")
	if !strings.HasPrefix(walletAddr, "0x") || len(walletAddr) != 42 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid wallet address"})
		return
	}

	nonceBytes := make([]byte, 32)
	rand.Read(nonceBytes)
	nonce := hex.EncodeToString(nonceBytes)

	message := "Welcome to 链识数藏!\n\nPlease sign this message to verify your wallet ownership.\n\nNonce: " + nonce + "\n\nWallet: " + walletAddr

	var user models.User
	result := h.db.Where("wallet_address = ?", walletAddr).First(&user)
	if result.Error != nil {
		user = models.User{WalletAddress: walletAddr, Nonce: nonce}
		h.db.Create(&user)
	} else {
		h.db.Model(&user).Update("nonce", nonce)
	}

	c.JSON(http.StatusOK, NonceResponse{
		Nonce:      nonce,
		WalletAddr: walletAddr,
		Message:    message,
	})
}

func (h *AuthHandler) Login(c *gin.Context) {
	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	req.WalletAddress = strings.ToLower(req.WalletAddress)

	var user models.User
	if err := h.db.Where("wallet_address = ?", req.WalletAddress).First(&user).Error; err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "user not found, request nonce first"})
		return
	}

	sigBytes, err := hexutil.Decode(req.Signature)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid signature format"})
		return
	}

	if sigBytes[64] != 27 && sigBytes[64] != 28 {
		sigBytes[64] -= 27
	}

	signerPubKey, err := crypto.SigToPub(
		crypto.Keccak256Hash([]byte(req.Message)).Bytes(),
		sigBytes,
	)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "signature verification failed"})
		return
	}

	signerAddr := crypto.PubkeyToAddress(*signerPubKey).Hex()
	if strings.ToLower(signerAddr) != req.WalletAddress {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "signature does not match wallet address"})
		return
	}

	claims := &middleware.Claims{
		UserID:        user.ID,
		WalletAddress: user.WalletAddress,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(72 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString([]byte(h.cfg.JWTSecret))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to generate token"})
		return
	}

	h.db.Model(&user).Update("nonce", "")

	c.JSON(http.StatusOK, LoginResponse{
		Token:    tokenString,
		UserID:   user.ID,
		Nickname: user.Nickname,
	})
}

func (h *AuthHandler) GetProfile(c *gin.Context) {
	userID := c.GetUint("user_id")
	var user models.User
	if err := h.db.First(&user, userID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "user not found"})
		return
	}

	c.JSON(http.StatusOK, user)
}

func (h *AuthHandler) UpdateProfile(c *gin.Context) {
	userID := c.GetUint("user_id")
	var updates map[string]interface{}
	if err := c.ShouldBindJSON(&updates); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	allowed := map[string]bool{"nickname": true, "avatar": true, "bio": true}
	filtered := make(map[string]interface{})
	for k, v := range updates {
		if allowed[k] {
			filtered[k] = v
		}
	}

	if err := h.db.Model(&models.User{}).Where("id = ?", userID).Updates(filtered).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "update failed"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "profile updated"})
}

func (h *AuthHandler) GetUserByAddress(c *gin.Context) {
	address := strings.ToLower(c.Param("address"))
	var user models.User
	if err := h.db.Where("wallet_address = ?", address).First(&user).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "user not found"})
		return
	}
	c.JSON(http.StatusOK, user)
}
