import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ApiError } from '../api/client';
import { clearStoredInventoryToken, getStoredInventoryToken, storeInventoryToken } from '../api/auth';
import {
  generateCollectionCard,
  getCollectionCardStatus,
  getCollections,
  prepareCollectionMint,
  updateCollection,
  uploadCollectionImage,
} from '../api/inventory';
import {
  adaptCardStatusIntoItem,
  adaptCollectionDetailPatch,
  adaptCollectionToInventoryItem,
  buildInventoryDashboardData,
  toInventoryCardStatus,
} from './adapters';
import { inventoryDemoData } from '../../data/inventoryDemoData';
import type {
  BackendCardStatusResponse,
  InventoryActionKind,
  InventoryActionNotice,
  InventoryConversionState,
  InventoryDashboardData,
  InventoryDataSource,
  InventoryItemViewModel,
} from '../../types/inventory';

const DEFAULT_STYLE_PROMPT =
  'Holographic frosted neon sci-fi collectible card, cyan and blue glow, dark glassmorphism vault interface, premium cyberpunk display.';
const CARD_POLL_INTERVAL_MS = 2500;
const CARD_POLL_TIMEOUT_MS = 120000;
const COLLECTION_POLL_INTERVAL_MS = 2500;
const COLLECTION_POLL_TIMEOUT_MS = 90000;

interface InventoryActionState {
  kind: InventoryActionKind;
  collectionId?: number;
}

export interface UseInventoryDataResult {
  data: InventoryDashboardData;
  loading: boolean;
  error: string | null;
  token: string;
  dataSource: InventoryDataSource;
  notice: InventoryActionNotice | null;
  actionState: InventoryActionState | null;
  conversionState: InventoryConversionState;
  guidedStage: 'upload' | 'review' | 'card' | 'mint';
  guidedCollectionId?: number;
  setGuidedStage: (stage: 'upload' | 'review' | 'card' | 'mint') => void;
  setToken: (token: string) => void;
  clearToken: () => void;
  refresh: () => Promise<void>;
  generateCardForItem: (collectionId: number) => Promise<void>;
  prepareMintForItem: (collectionId: number) => Promise<void>;
  viewTokenUriForItem: (tokenUri?: string) => Promise<void>;
  uploadCollection: (file: File) => Promise<void>;
  oneClickConvert: (collectionId: number) => Promise<void>;
  saveCollectionMetadata: (
    collectionId: number,
    payload: {
      attributes: {
        ip_name: string;
        series: string;
        material: string;
        dominant_colors: string[];
        condition: string;
        style_tags: string[];
      };
      physical_location: string;
    },
  ) => Promise<void>;
}

const INITIAL_CONVERSION_STATE: InventoryConversionState = {
  uploadStatus: 'idle',
  aiStatus: 'idle',
  cardStatus: 'idle',
  mintStatus: 'idle',
};

export function useInventoryData(): UseInventoryDataResult {
  const [token, setTokenState] = useState('');
  const [data, setData] = useState<InventoryDashboardData>(inventoryDemoData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState<InventoryDataSource>('demo');
  const [notice, setNotice] = useState<InventoryActionNotice | null>(null);
  const [actionState, setActionState] = useState<InventoryActionState | null>(null);
  const [conversionState, setConversionState] = useState<InventoryConversionState>(INITIAL_CONVERSION_STATE);
  const { t } = useTranslation();
  const [guidedStage, setGuidedStage] = useState<'upload' | 'review' | 'card' | 'mint'>('upload');
  const [guidedCollectionId, setGuidedCollectionId] = useState<number | undefined>(undefined);

  useEffect(() => {
    setTokenState(getStoredInventoryToken());
  }, []);

  const loadInventory = useCallback(async (authToken: string) => {
    if (!authToken) {
      setData(inventoryDemoData);
      setDataSource('demo');
      setError(t('hooks.useInventoryData.noTokenInfo'));
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await getCollections(authToken);
      const items = response.collections.map(adaptCollectionToInventoryItem);

      const nextData = buildInventoryDashboardData(items);

      setData(nextData);
      setDataSource('backend');
    } catch (requestError) {
      setData(inventoryDemoData);
      setDataSource('demo');
      setError(toReadableError(requestError, 'Failed to load live inventory data.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInventory(token);
  }, [loadInventory, token]);

  const refresh = useCallback(async () => {
    setActionState({ kind: 'refresh' });
    try {
      await loadInventory(token);
      if (token) {
        setNotice({ tone: 'success', message: t('hooks.useInventoryData.refreshSuccess') });
      }
    } finally {
      setActionState(null);
    }
  }, [loadInventory, token]);

  const setToken = useCallback((nextToken: string) => {
    storeInventoryToken(nextToken);
    setTokenState(nextToken.trim());
    setNotice({ tone: 'success', message: t('hooks.useInventoryData.jwtSaved') });
  }, []);

  const clearToken = useCallback(() => {
    clearStoredInventoryToken();
    setTokenState('');
    setNotice({ tone: 'info', message: t('hooks.useInventoryData.tokenCleared') });
  }, []);

  const updateItem = useCallback(
    (collectionId: number, transform: (item: InventoryItemViewModel) => InventoryItemViewModel) => {
      setData((current) => {
        const nextItems = current.items.map((item) =>
          item.collectionId === collectionId ? transform(item) : item,
        );
        return {
          ...current,
          ...buildInventoryDashboardData(nextItems),
        };
      });
    },
    [],
  );

  const generateCardForItem = useCallback(
    async (collectionId: number) => {
      if (!token) {
        setNotice({ tone: 'error', message: t('hooks.useInventoryData.noTokenGenerateCard') });
        return;
      }

      setActionState({ kind: 'generate_card', collectionId });
      setNotice({ tone: 'info', message: t('hooks.useInventoryData.cardGenerating') });

      try {
        await generateCollectionCard(token, collectionId, DEFAULT_STYLE_PROMPT);
        const status = await pollCardStatus(token, collectionId, t);
        updateItem(collectionId, (item) => adaptCardStatusIntoItem(item, status));
        setConversionState((current) => ({
          ...current,
          collectionId,
          cardStatus: toInventoryCardStatus(status.card_generation_status),
        }));
        setGuidedCollectionId(collectionId);
        setGuidedStage('mint');
        await loadInventory(token);
        setNotice({ tone: 'success', message: t('hooks.useInventoryData.cardGenerated') });
      } catch (requestError) {
        setNotice({ tone: 'error', message: toReadableError(requestError, t('hooks.useInventoryData.generateCardFailed')) });
      } finally {
        setActionState(null);
      }
    },
    [loadInventory, token, updateItem],
  );

  const prepareMintForItem = useCallback(
    async (collectionId: number) => {
      if (!token) {
        setNotice({ tone: 'error', message: t('hooks.useInventoryData.noTokenPrepareMint') });
        return;
      }

      setActionState({ kind: 'prepare_mint', collectionId });
      setNotice({ tone: 'info', message: t('hooks.useInventoryData.preparingMint') });

      try {
        const result = await prepareCollectionMint(token, collectionId);
        updateItem(collectionId, (item) =>
          adaptCollectionDetailPatch(item, {
            token_uri: result.tokenURI,
            status: result.status,
            royalty_fee: result.royaltyFee,
          }),
        );
        setConversionState((current) => ({
          ...current,
          collectionId,
          mintStatus: 'prepared',
          tokenUri: result.tokenURI,
        }));
        setGuidedCollectionId(collectionId);
        setGuidedStage('mint');
        await loadInventory(token);
        setNotice({ tone: 'success', message: t('hooks.useInventoryData.mintPrepCompleted') });
      } catch (requestError) {
        setConversionState((current) => ({
          ...current,
          mintStatus: 'failed',
        }));
        setNotice({ tone: 'error', message: toReadableError(requestError, t('hooks.useInventoryData.prepareMintFailed')) });
      } finally {
        setActionState(null);
      }
    },
    [loadInventory, token, updateItem],
  );

  const viewTokenUriForItem = useCallback(async (tokenUri?: string) => {
    if (!tokenUri) {
      setNotice({ tone: 'error', message: t('hooks.useInventoryData.noTokenUri') });
      return;
    }

    if (/^https?:\/\//i.test(tokenUri)) {
      window.open(tokenUri, '_blank', 'noopener,noreferrer');
      setNotice({ tone: 'success', message: t('hooks.useInventoryData.tokenUriOpened') });
      return;
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(tokenUri);
        setNotice({ tone: 'success', message: t('hooks.useInventoryData.tokenUriCopied') });
        return;
      }
    } catch {
      // fall through to inline notice below
    }

    setNotice({ tone: 'info', message: t('hooks.useInventoryData.tokenUriLabel', { uri: tokenUri }) });
  }, []);

  const uploadCollection = useCallback(
    async (file: File) => {
      if (!token) {
        setNotice({ tone: 'error', message: t('hooks.useInventoryData.noTokenUpload') });
        return;
      }

      setActionState({ kind: 'upload_collection' });
      setGuidedStage('upload');
      setConversionState({
        uploadedFileName: file.name,
        uploadStatus: 'uploading',
        aiStatus: 'pending',
        cardStatus: 'idle',
        mintStatus: 'idle',
      });
      setNotice({ tone: 'info', message: t('hooks.useInventoryData.uploading') });

      try {
        const response = await uploadCollectionImage(token, file);
        setConversionState((current) => ({
          ...current,
          collectionId: response.collection_id,
          uploadStatus: 'uploaded',
          aiStatus: 'pending',
        }));
        setGuidedCollectionId(response.collection_id);

        const createdItem = await pollCollectionUntilStored(token, response.collection_id, t);
        setConversionState((current) => ({
          ...current,
          aiStatus: createdItem.status === 'failed' ? 'failed' : 'stored',
          cardStatus: createdItem.cardGenerationStatus,
          tokenUri: createdItem.tokenUri,
        }));

        await loadInventory(token);
        setGuidedStage(createdItem.status === 'failed' ? 'upload' : 'review');
        setNotice({ tone: 'success', message: t('hooks.useInventoryData.uploadSuccess') });
      } catch (requestError) {
        setConversionState((current) => ({
          ...current,
          uploadStatus: 'failed',
          aiStatus: 'failed',
        }));
        setNotice({ tone: 'error', message: toReadableError(requestError, t('hooks.useInventoryData.uploadFailed')) });
      } finally {
        setActionState(null);
      }
    },
    [loadInventory, token],
  );

  const oneClickConvert = useCallback(
    async (collectionId: number) => {
      if (!token) {
        setNotice({ tone: 'error', message: t('hooks.useInventoryData.noTokenOneClick') });
        return;
      }

      setActionState({ kind: 'one_click_convert', collectionId });
      setNotice({ tone: 'info', message: t('hooks.useInventoryData.oneClickRunning') });
      setConversionState((current) => ({
        ...current,
        collectionId,
        aiStatus: current.aiStatus === 'idle' ? 'stored' : current.aiStatus,
      }));
      setGuidedCollectionId(collectionId);

      try {
        await generateCollectionCard(token, collectionId, DEFAULT_STYLE_PROMPT);
        const cardStatus = await pollCardStatus(token, collectionId, t);
        setConversionState((current) => ({
          ...current,
          cardStatus: toInventoryCardStatus(cardStatus.card_generation_status),
          mintStatus: 'preparing',
        }));

        const mintResult = await prepareCollectionMint(token, collectionId);
        setConversionState((current) => ({
          ...current,
          mintStatus: 'prepared',
          tokenUri: mintResult.tokenURI,
        }));
        setGuidedStage('mint');
        await loadInventory(token);
        setNotice({ tone: 'success', message: t('hooks.useInventoryData.oneClickSuccess') });
      } catch (requestError) {
        setConversionState((current) => ({
          ...current,
          mintStatus: 'failed',
        }));
        setNotice({ tone: 'error', message: toReadableError(requestError, t('hooks.useInventoryData.oneClickFailed')) });
      } finally {
        setActionState(null);
      }
    },
    [loadInventory, token],
  );

  const saveCollectionMetadata = useCallback(
    async (
      collectionId: number,
      payload: {
        attributes: {
          ip_name: string;
          series: string;
          material: string;
          dominant_colors: string[];
          condition: string;
          style_tags: string[];
        };
        physical_location: string;
      },
    ) => {
      if (!token) {
        setNotice({ tone: 'error', message: t('hooks.useInventoryData.noTokenSave') });
        return;
      }

      setActionState({ kind: 'refresh', collectionId });
      setNotice({ tone: 'info', message: t('hooks.useInventoryData.savingMetadata') });

      try {
        const updated = await updateCollection(token, collectionId, payload);
        const updatedItem = adaptCollectionToInventoryItem(updated as never);
        updateItem(collectionId, () => updatedItem);
        setConversionState((current) => ({
          ...current,
          collectionId,
          aiStatus: 'stored',
        }));
        setGuidedCollectionId(collectionId);
        setGuidedStage('card');
        await loadInventory(token);
        setNotice({ tone: 'success', message: t('hooks.useInventoryData.metadataSaved') });
      } catch (requestError) {
        setNotice({ tone: 'error', message: toReadableError(requestError, t('hooks.useInventoryData.saveMetadataFailed')) });
      } finally {
        setActionState(null);
      }
    },
    [loadInventory, token, updateItem],
  );

  return useMemo(
    () => ({
      data,
      loading,
      error,
      token,
      dataSource,
      notice,
      actionState,
      conversionState,
      guidedStage,
      guidedCollectionId,
      setGuidedStage,
      setToken,
      clearToken,
      refresh,
      generateCardForItem,
      prepareMintForItem,
      viewTokenUriForItem,
      uploadCollection,
      oneClickConvert,
      saveCollectionMetadata,
    }),
    [
      actionState,
      clearToken,
      conversionState,
      data,
      dataSource,
      error,
      generateCardForItem,
      guidedCollectionId,
      guidedStage,
      loading,
      notice,
      oneClickConvert,
      prepareMintForItem,
      refresh,
      saveCollectionMetadata,
      setGuidedStage,
      setToken,
      token,
      uploadCollection,
      viewTokenUriForItem,
    ],
  );
}

async function pollCardStatus(token: string, collectionId: number, t: (key: string) => string): Promise<BackendCardStatusResponse> {
  const startedAt = Date.now();

  while (Date.now() - startedAt < CARD_POLL_TIMEOUT_MS) {
    const status = await getCollectionCardStatus(token, collectionId);
    if (status.card_generation_status !== 'GENERATING' && status.card_generation_status !== 'PENDING') {
      return status;
    }

    await new Promise((resolve) => window.setTimeout(resolve, CARD_POLL_INTERVAL_MS));
  }

  throw new Error(t('hooks.useInventoryData.cardPollTimeout'));
}

async function pollCollectionUntilStored(token: string, collectionId: number, t: (key: string) => string): Promise<InventoryItemViewModel> {
  const startedAt = Date.now();

  while (Date.now() - startedAt < COLLECTION_POLL_TIMEOUT_MS) {
    const response = await getCollections(token);
    const match = response.collections.find((collection) => collection.id === collectionId);
    if (match) {
      const item = adaptCollectionToInventoryItem(match);
      if (item.status !== 'pending_ai') {
        return item;
      }
    }

    await new Promise((resolve) => window.setTimeout(resolve, COLLECTION_POLL_INTERVAL_MS));
  }

  throw new Error(t('hooks.useInventoryData.collectionPollTimeout'));
}

function toReadableError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}
