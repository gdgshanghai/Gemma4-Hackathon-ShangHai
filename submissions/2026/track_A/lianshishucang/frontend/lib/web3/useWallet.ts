import { useCallback, useEffect, useMemo, useState } from 'react';
import { createWalletClient, custom, getAddress } from 'viem';
import { sepolia, mainnet } from 'viem/chains';
import { SUPPORTED_CHAIN_ID, CHAIN_CONFIG, hardhatLocal } from './config';

const CHAIN_MAP: Record<number, typeof sepolia> = {
  1: mainnet as unknown as typeof sepolia,
  11155111: sepolia,
  31337: hardhatLocal as unknown as typeof sepolia,
};

export interface WalletState {
  address: string;
  chainId: number;
  isConnected: boolean;
  isCorrectChain: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  switchChain: () => Promise<void>;
  formatAddress: (addr: string) => string;
}

export function useWallet(): WalletState {
  const [address, setAddress] = useState<string>('');
  const [chainId, setChainId] = useState<number>(0);

  const isCorrectChain = SUPPORTED_CHAIN_ID === 0 || chainId === SUPPORTED_CHAIN_ID;

  const getWalletClient = useCallback(() => {
    if (typeof window === 'undefined' || !window.ethereum) {
      return null;
    }
    const chain = CHAIN_MAP[SUPPORTED_CHAIN_ID] || sepolia;
    return createWalletClient({
      chain,
      transport: custom(window.ethereum),
    });
  }, []);

  const updateAccounts = useCallback(async () => {
    try {
      const wc = getWalletClient();
      if (!wc) return;
      const accounts = await wc.getAddresses();
      if (accounts.length > 0) {
        setAddress(getAddress(accounts[0]));
      } else {
        setAddress('');
      }
    } catch {
      setAddress('');
    }
  }, [getWalletClient]);

  const updateChainId = useCallback(async () => {
    try {
      const wc = getWalletClient();
      if (!wc) return;
      const id = await wc.getChainId();
      setChainId(id);
    } catch {
      // ignore
    }
  }, [getWalletClient]);

  const connect = useCallback(async () => {
    try {
      const wc = getWalletClient();
      if (!wc) {
        window.open('https://metamask.io/download/', '_blank');
        return;
      }
      const accounts = await wc.requestAddresses();
      if (accounts.length > 0) {
        setAddress(getAddress(accounts[0]));
      }
      await updateChainId();
    } catch {
      // user rejected or error
    }
  }, [getWalletClient, updateChainId]);

  const disconnect = useCallback(() => {
    setAddress('');
  }, []);

  const switchChain = useCallback(async () => {
    if (typeof window === 'undefined' || !window.ethereum) return;
    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: `0x${SUPPORTED_CHAIN_ID.toString(16)}` }],
      });
    } catch (switchError: unknown) {
      const err = switchError as { code?: number };
      if (err.code === 4902) {
        const config = CHAIN_CONFIG[SUPPORTED_CHAIN_ID];
        if (config) {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [
              {
                chainId: `0x${SUPPORTED_CHAIN_ID.toString(16)}`,
                chainName: config.name,
                nativeCurrency: { name: config.currency, symbol: config.currency, decimals: 18 },
                rpcUrls: [config.rpc],
              },
            ],
          });
        }
      }
    }
    await updateChainId();
  }, [updateChainId]);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.ethereum) return;

    updateAccounts();
    updateChainId();

    const handleAccountsChanged = (...args: unknown[]) => {
      const accounts = args[0] as string[];
      if (accounts.length === 0) {
        setAddress('');
      } else {
        setAddress(getAddress(accounts[0]));
      }
    };

    const handleChainChanged = () => {
      setTimeout(() => {
        updateChainId();
      }, 300);
    };

    window.ethereum.on('accountsChanged', handleAccountsChanged);
    window.ethereum.on('chainChanged', handleChainChanged);

    return () => {
      window.ethereum?.removeListener('accountsChanged', handleAccountsChanged);
      window.ethereum?.removeListener('chainChanged', handleChainChanged);
    };
  }, [updateAccounts, updateChainId]);

  const formatAddress = useCallback((addr: string) => {
    if (!addr || addr.length < 10) return addr;
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  }, []);

  return useMemo(
    () => ({
      address,
      chainId,
      isConnected: address.length > 0,
      isCorrectChain,
      connect,
      disconnect,
      switchChain,
      formatAddress,
    }),
    [address, chainId, isCorrectChain, connect, disconnect, switchChain, formatAddress],
  );
}
