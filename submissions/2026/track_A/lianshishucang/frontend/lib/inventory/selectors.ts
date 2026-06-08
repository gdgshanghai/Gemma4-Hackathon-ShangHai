import type {
  InventoryCardFilterStatus,
  InventoryFilterStatus,
  InventoryItemViewModel,
  InventorySortBy,
} from '../../types/inventory';

interface InventoryFilterParams {
  searchQuery: string;
  statusFilter: InventoryFilterStatus;
  cardFilter: InventoryCardFilterStatus;
  sortBy: InventorySortBy;
}

export function filterAndSortInventoryItems(
  items: InventoryItemViewModel[],
  params: InventoryFilterParams,
): InventoryItemViewModel[] {
  const normalizedQuery = params.searchQuery.trim().toLowerCase();

  return [...items]
    .filter((item) => {
      if (params.statusFilter !== 'all' && item.status !== params.statusFilter) {
        return false;
      }

      if (params.cardFilter !== 'all' && item.cardGenerationStatus !== params.cardFilter) {
        return false;
      }

      if (!normalizedQuery) {
        return true;
      }

      const haystack = [
        item.name,
        item.displayCode,
        item.statusLabel,
        item.cardStatusLabel,
        item.physicalLocation,
        ...item.attributes.map((attribute) => `${attribute.trait_type} ${attribute.value}`),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();

      return haystack.includes(normalizedQuery);
    })
    .sort((left, right) => compareInventoryItems(left, right, params.sortBy));
}

export function getPrimarySelection(
  items: InventoryItemViewModel[],
  selectedId?: string,
): InventoryItemViewModel | undefined {
  return items.find((item) => item.id === selectedId) ?? items[0];
}

function compareInventoryItems(
  left: InventoryItemViewModel,
  right: InventoryItemViewModel,
  sortBy: InventorySortBy,
): number {
  switch (sortBy) {
    case 'created_desc':
      return compareDates(right.createdAt, left.createdAt) || right.collectionId - left.collectionId;
    case 'name_asc':
      return left.name.localeCompare(right.name) || left.collectionId - right.collectionId;
    case 'status':
      return (
        left.statusLabel.localeCompare(right.statusLabel) ||
        left.cardStatusLabel.localeCompare(right.cardStatusLabel) ||
        left.name.localeCompare(right.name)
      );
    case 'updated_desc':
    default:
      return compareDates(right.updatedAt, left.updatedAt) || right.collectionId - left.collectionId;
  }
}

function compareDates(left?: string, right?: string): number {
  return toTimestamp(left) - toTimestamp(right);
}

function toTimestamp(value?: string): number {
  if (!value) {
    return 0;
  }

  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}
