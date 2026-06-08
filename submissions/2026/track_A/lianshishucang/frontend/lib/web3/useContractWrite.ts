import i18n from '../../lib/i18n/i18n';
import { useCallback } from 'react';
import {
  createWalletClient,
  createPublicClient,
  custom,
  http,
  type Address,
} from 'viem';
import { sepolia, mainnet } from 'viem/chains';
import { NFT_ABI, MARKETPLACE_ABI, ERC721_ABI } from './abi';
import {
  NFT_CONTRACT_ADDRESS,
  MARKETPLACE_CONTRACT_ADDRESS,
  SUPPORTED_CHAIN_ID,
  CHAIN_CONFIG,
  hardhatLocal,
} from './config';

const CHAIN_MAP: Record<number, typeof sepolia> = {
  1: mainnet as unknown as typeof sepolia,
  11155111: sepolia,
  31337: hardhatLocal as unknown as typeof sepolia,
};

function getClients() {
  if (typeof window === 'undefined' || !window.ethereum) return null;
  const chain = CHAIN_MAP[SUPPORTED_CHAIN_ID] || sepolia;
  const config = CHAIN_CONFIG[SUPPORTED_CHAIN_ID];
  const walletClient = createWalletClient({ chain, transport: custom(window.ethereum) });
  const publicClient = createPublicClient({
    chain,
    transport: config?.rpc ? http(config.rpc) : http(),
  });
  return { walletClient, publicClient };
}

export function useContractWrite() {
  const mintNFT = useCallback(
    async (to: string, tokenUri: string, royaltyFee: number): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: NFT_CONTRACT_ADDRESS as Address,
        abi: NFT_ABI,
        functionName: 'mint',
        args: [to as Address, tokenUri, BigInt(royaltyFee)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const createListing = useCallback(
    async (nftContract: string, tokenId: number, priceWei: string): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: MARKETPLACE_CONTRACT_ADDRESS as Address,
        abi: MARKETPLACE_ABI,
        functionName: 'createListing',
        args: [nftContract as Address, BigInt(tokenId), BigInt(priceWei)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const cancelListing = useCallback(
    async (listingId: number): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: MARKETPLACE_CONTRACT_ADDRESS as Address,
        abi: MARKETPLACE_ABI,
        functionName: 'cancelListing',
        args: [BigInt(listingId)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const buyItem = useCallback(
    async (listingId: number, valueWei: string): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: MARKETPLACE_CONTRACT_ADDRESS as Address,
        abi: MARKETPLACE_ABI,
        functionName: 'buyItem',
        args: [BigInt(listingId)],
        value: BigInt(valueWei),
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const approveNFT = useCallback(
    async (nftContract: string, operator: string, tokenId: number): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: nftContract as Address,
        abi: ERC721_ABI,
        functionName: 'approve',
        args: [operator as Address, BigInt(tokenId)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const setApprovalForAll = useCallback(
    async (nftContract: string, operator: string, approved: boolean): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: nftContract as Address,
        abi: ERC721_ABI,
        functionName: 'setApprovalForAll',
        args: [operator as Address, approved],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const updatePrice = useCallback(
    async (listingId: number, newPriceWei: string): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: MARKETPLACE_CONTRACT_ADDRESS as Address,
        abi: MARKETPLACE_ABI,
        functionName: 'updatePrice',
        args: [BigInt(listingId), BigInt(newPriceWei)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const createOffer = useCallback(
    async (nftContract: string, tokenId: number, priceWei: string, expiration: number): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: MARKETPLACE_CONTRACT_ADDRESS as Address,
        abi: MARKETPLACE_ABI,
        functionName: 'createOffer',
        args: [nftContract as Address, BigInt(tokenId), BigInt(priceWei), BigInt(expiration)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const cancelOffer = useCallback(
    async (tokenId: number, offerIndex: number): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: MARKETPLACE_CONTRACT_ADDRESS as Address,
        abi: MARKETPLACE_ABI,
        functionName: 'cancelOffer',
        args: [BigInt(tokenId), BigInt(offerIndex)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const acceptOffer = useCallback(
    async (nftContract: string, tokenId: number, offerIndex: number): Promise<`0x${string}`> => {
      const clients = getClients();
      if (!clients) throw new Error(i18n.t('common.walletNotConnected'));
      const { walletClient, publicClient } = clients;
      const accounts = await walletClient.requestAddresses();
      const hash = await walletClient.writeContract({
        address: MARKETPLACE_CONTRACT_ADDRESS as Address,
        abi: MARKETPLACE_ABI,
        functionName: 'acceptOffer',
        args: [nftContract as Address, BigInt(tokenId), BigInt(offerIndex)],
        account: accounts[0],
      });
      await publicClient.waitForTransactionReceipt({ hash });
      return hash;
    },
    [],
  );

  const getOffersForToken = useCallback(
    async (tokenId: number): Promise<any[]> => {
      const clients = getClients();
      if (!clients) return [];
      const { publicClient } = clients;
      try {
        const result = await publicClient.readContract({
          address: MARKETPLACE_CONTRACT_ADDRESS as Address,
          abi: MARKETPLACE_ABI,
          functionName: 'getOffers',
          args: [BigInt(tokenId)],
        });
        return result as any[];
      } catch {
        return [];
      }
    },
    [],
  );

  const getListingByToken = useCallback(
    async (tokenId: number): Promise<any | null> => {
      const clients = getClients();
      if (!clients) return null;
      const { publicClient } = clients;
      try {
        const result = await publicClient.readContract({
          address: MARKETPLACE_CONTRACT_ADDRESS as Address,
          abi: MARKETPLACE_ABI,
          functionName: 'getListingByToken',
          args: [BigInt(tokenId)],
        });
        return result;
      } catch {
        return null;
      }
    },
    [],
  );

  return {
    mintNFT,
    createListing,
    cancelListing,
    buyItem,
    approveNFT,
    setApprovalForAll,
    updatePrice,
    createOffer,
    cancelOffer,
    acceptOffer,
    getOffersForToken,
    getListingByToken,
  };
}
