package services

import (
	"context"
	"crypto/ecdsa"
	"math/big"
	"strings"

	"github.com/ethereum/go-ethereum"
	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/crypto"
	"github.com/ethereum/go-ethereum/ethclient"
)

type BlockchainService struct {
	client            *ethclient.Client
	chainID           *big.Int
	privateKey        *ecdsa.PrivateKey
	fromAddress       common.Address
	nftABI            abi.ABI
	marketplaceABI    abi.ABI
	nftAddress        common.Address
	marketplaceAddress common.Address
}

func NewBlockchainService(
	rpcURL string,
	chainID int64,
	privateKeyHex string,
	nftABIStr, marketplaceABIStr string,
	nftAddr, marketplaceAddr string,
) (*BlockchainService, error) {
	client, err := ethclient.Dial(rpcURL)
	if err != nil {
		return nil, err
	}

	nftABI, err := abi.JSON(strings.NewReader(nftABIStr))
	if err != nil {
		return nil, err
	}

	marketplaceABI, err := abi.JSON(strings.NewReader(marketplaceABIStr))
	if err != nil {
		return nil, err
	}

	var pk *ecdsa.PrivateKey
	var fromAddr common.Address
	if privateKeyHex != "" {
		pk, err = crypto.HexToECDSA(privateKeyHex)
		if err != nil {
			return nil, err
		}
		fromAddr = crypto.PubkeyToAddress(pk.PublicKey)
	}

	return &BlockchainService{
		client:             client,
		chainID:            big.NewInt(chainID),
		privateKey:         pk,
		fromAddress:        fromAddr,
		nftABI:             nftABI,
		marketplaceABI:     marketplaceABI,
		nftAddress:         common.HexToAddress(nftAddr),
		marketplaceAddress: common.HexToAddress(marketplaceAddr),
	}, nil
}

func (s *BlockchainService) GetClient() *ethclient.Client {
	return s.client
}

func (s *BlockchainService) GetNFTAddress() common.Address {
	return s.nftAddress
}

func (s *BlockchainService) GetMarketplaceAddress() common.Address {
	return s.marketplaceAddress
}

func (s *BlockchainService) sendTransaction(to common.Address, data []byte, value *big.Int) (*types.Transaction, error) {
	if s.privateKey == nil {
		return nil, nil
	}

	nonce, err := s.client.PendingNonceAt(context.Background(), s.fromAddress)
	if err != nil {
		return nil, err
	}

	gasTipCap, err := s.client.SuggestGasTipCap(context.Background())
	if err != nil {
		gasTipCap = big.NewInt(1e9)
	}

	gasFeeCap, err := s.client.SuggestGasPrice(context.Background())
	if err != nil {
		gasFeeCap = big.NewInt(2e10)
	}

	msg := ethereum.CallMsg{
		From:  s.fromAddress,
		To:    &to,
		Value: value,
		Data:  data,
	}

	gasLimit, err := s.client.EstimateGas(context.Background(), msg)
	if err != nil {
		return nil, err
	}

	tx := types.NewTx(&types.DynamicFeeTx{
		ChainID:   s.chainID,
		Nonce:     nonce,
		GasFeeCap: gasFeeCap,
		GasTipCap: gasTipCap,
		Gas:       gasLimit,
		To:        &to,
		Value:     value,
		Data:      data,
	})

	signedTx, err := types.SignTx(tx, types.LatestSignerForChainID(s.chainID), s.privateKey)
	if err != nil {
		return nil, err
	}

	return signedTx, s.client.SendTransaction(context.Background(), signedTx)
}

func (s *BlockchainService) callContract(to common.Address, data []byte) ([]byte, error) {
	msg := ethereum.CallMsg{
		To:   &to,
		Data: data,
	}
	return s.client.CallContract(context.Background(), msg, nil)
}
