import { apiRequest } from './client';
import type {
  BackendCardStatusResponse,
  BackendCollectionListResponse,
  BackendGenerateCardResponse,
  BackendMarketplaceListingListResponse,
  BackendNFT,
  BackendNFTListResponse,
  BackendPrepareMintResponse,
  BackendUploadCollectionResponse,
} from '../../types/inventory';

export async function getCollections(token: string) {
  return apiRequest<BackendCollectionListResponse>('/api/v1/collections', { method: 'GET' }, { token });
}

export async function uploadCollectionImage(token: string, file: File) {
  const formData = new FormData();
  formData.append('image', file);

  return apiRequest<BackendUploadCollectionResponse>(
    '/api/v1/collections/upload',
    {
      method: 'POST',
      body: formData,
    },
    { token },
  );
}

export async function updateCollection(
  token: string,
  collectionId: number,
  payload: {
    attributes?: {
      ip_name: string;
      series: string;
      material: string;
      dominant_colors: string[];
      condition: string;
      style_tags: string[];
    };
    physical_location?: string;
  },
) {
  return apiRequest(`/api/v1/collections/${collectionId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }, { token });
}

export async function generateCollectionCard(
  token: string,
  collectionId: number,
  stylePrompt: string,
) {
  return apiRequest<BackendGenerateCardResponse>(
    `/api/v1/collections/${collectionId}/generate-card`,
    {
      method: 'POST',
      body: JSON.stringify({ style_prompt: stylePrompt }),
    },
    { token },
  );
}

export async function getCollectionCardStatus(token: string, collectionId: number) {
  return apiRequest<BackendCardStatusResponse>(
    `/api/v1/collections/${collectionId}/card-status`,
    { method: 'GET' },
    { token },
  );
}

export async function prepareCollectionMint(token: string, collectionId: number) {
  return apiRequest<BackendPrepareMintResponse>(
    `/api/v1/collections/${collectionId}/prepare-mint`,
    { method: 'POST' },
    { token },
  );
}

export async function getNFT(token: string, nftId: number) {
  return apiRequest<BackendNFT>(`/api/v1/nfts/${nftId}`, { method: 'GET' }, { token });
}

export async function getMyOwnedNFTs(
  token: string,
  params: { page?: number; pageSize?: number } = {},
) {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });

  return apiRequest<BackendNFTListResponse>(
    `/api/v1/nfts/my/owned?${searchParams.toString()}`,
    { method: 'GET' },
    { token },
  );
}

export async function getMyCreatedNFTs(
  token: string,
  params: { page?: number; pageSize?: number } = {},
) {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });

  return apiRequest<BackendNFTListResponse>(
    `/api/v1/nfts/my/created?${searchParams.toString()}`,
    { method: 'GET' },
    { token },
  );
}

export async function getMarketplaceListings(
  token: string,
  params: { page?: number; pageSize?: number } = {},
) {
  const searchParams = new URLSearchParams({
    page: String(params.page ?? 1),
    page_size: String(params.pageSize ?? 20),
  });

  return apiRequest<BackendMarketplaceListingListResponse>(
    `/api/v1/marketplace/listings?${searchParams.toString()}`,
    { method: 'GET' },
    { token },
  );
}


