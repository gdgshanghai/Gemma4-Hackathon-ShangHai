import { defineChain } from 'viem';
import i18n from '../../lib/i18n/i18n';

export const SUPPORTED_CHAIN_ID = Number(import.meta.env.VITE_CHAIN_ID) || 11155111;

export const NFT_CONTRACT_ADDRESS =
  (import.meta.env.VITE_NFT_CONTRACT as string) || '';

export const MARKETPLACE_CONTRACT_ADDRESS =
  (import.meta.env.VITE_MARKETPLACE_CONTRACT as string) || '';

export const CHAIN_CONFIG: Record<number, { name: string; currency: string; rpc: string }> = {
  1: { name: i18n.t('config.mainnet'), currency: i18n.t('config.eth'), rpc: 'https://eth-mainnet.g.alchemy.com/v2/demo' },
  11155111: { name: i18n.t('config.sepolia'), currency: i18n.t('config.eth'), rpc: 'https://eth-sepolia.g.alchemy.com/v2/demo' },
  31337: { name: i18n.t('config.hardhatLocal'), currency: i18n.t('config.eth'), rpc: 'http://127.0.0.1:8545' },
};

export const hardhatLocal = /*#__PURE__*/ defineChain({
  id: 31337,
  name: 'Hardhat Local',
  nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: { default: { http: ['http://127.0.0.1:8545'] } },
});
