import InventoryItemActions from './InventoryItemActions';
import InventoryDetailPanel from './InventoryDetailPanel';
import InventoryTradingOverview from './InventoryTradingOverview';
import type {
  InventoryActionKind,
  InventoryActionNotice,
  InventoryDataSource,
  InventoryItemViewModel,
} from '../../types/inventory';
import type { WalletState } from '../../lib/web3/useWallet';

interface InventoryMintPrepPanelProps {
  selectedItem?: InventoryItemViewModel;
  onRefresh: () => void;
  onGenerateCard: (collectionId: number) => void;
  onPrepareMint: (collectionId: number) => void;
  onViewTokenUri: (tokenUri?: string) => void;
  onMintNFT?: () => Promise<void>;
  actionState?: {
    kind: InventoryActionKind;
    collectionId?: number;
  } | null;
  notice?: InventoryActionNotice | null;
  dataSource: InventoryDataSource;
  wallet?: WalletState;
}

export default function InventoryMintPrepPanel(props: InventoryMintPrepPanelProps) {
  return (
    <div className="space-y-6">
      <InventoryTradingOverview item={props.selectedItem} dataSource={props.dataSource} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="space-y-6">
          <InventoryItemActions {...props} />
        </div>
        <div className="space-y-6">
          <InventoryDetailPanel item={props.selectedItem} />
        </div>
      </div>
    </div>
  );
}
