import { Wallet, Unplug, AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { WalletState } from '../../lib/web3/useWallet';

interface InventoryWalletPanelProps {
  wallet: WalletState;
}

export default function InventoryWalletPanel({ wallet }: InventoryWalletPanelProps) {
  const { t } = useTranslation();
  return (
    <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-5">
      <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-cyan-300/65">
        {t('walletPanel.onchainWallet')}
      </p>

      <div className="mt-4 space-y-4">
        {!wallet.isConnected ? (
          <button
            type="button"
            onClick={wallet.connect}
            className="flex w-full items-center justify-center gap-3 rounded-2xl border border-cyan-300/20 bg-cyan-300/10 px-4 py-4 text-base font-medium text-cyan-100 transition hover:-translate-y-0.5 hover:shadow-[0_0_18px_rgba(34,211,238,0.18)]"
          >
            <Wallet size={18} />
            {t('walletPanel.connectMetaMask')}
          </button>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 rounded-[1.2rem] border border-cyan-400/15 bg-[#071523]/75 p-4">
              <div>
                <p className="text-base font-medium text-white">
                  {wallet.formatAddress(wallet.address)}
                </p>
                <p className="mt-1 text-sm text-slate-300/70">
                  {t('walletPanel.chainId')} {wallet.chainId}
                </p>
              </div>
              <span className="inline-flex shrink-0 rounded-full border border-emerald-300/25 bg-emerald-300/8 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-emerald-100">
                {t('walletPanel.connected')}
              </span>
            </div>

            {!wallet.isCorrectChain ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 rounded-[1.1rem] border border-yellow-300/20 bg-yellow-300/8 px-4 py-3 text-sm text-yellow-100">
                  <AlertTriangle size={15} />
                  {t('walletPanel.wrongNetwork')}
                </div>
                <button
                  type="button"
                  onClick={wallet.switchChain}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl border border-yellow-300/20 bg-yellow-300/10 px-4 py-3 text-base font-medium text-yellow-100 transition hover:-translate-y-0.5"
                >
                  {t('walletPanel.switchNetwork')}
                </button>
              </div>
            ) : null}

            <button
              type="button"
              onClick={wallet.disconnect}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-base font-medium text-slate-200 transition hover:border-rose-300/20 hover:bg-rose-300/8 hover:text-rose-100"
            >
              <Unplug size={16} />
              {t('walletPanel.disconnect')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
