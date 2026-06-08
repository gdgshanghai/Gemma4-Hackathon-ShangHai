const INVENTORY_JWT_STORAGE_KEY = 'inventory-demo.jwt';

export function getStoredInventoryToken(): string {
  if (typeof window === 'undefined') {
    return '';
  }

  return window.localStorage.getItem(INVENTORY_JWT_STORAGE_KEY)?.trim() || '';
}

export function storeInventoryToken(token: string): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(INVENTORY_JWT_STORAGE_KEY, token.trim());
}

export function clearStoredInventoryToken(): void {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.removeItem(INVENTORY_JWT_STORAGE_KEY);
}
