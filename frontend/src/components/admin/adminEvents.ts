export const IDENTITY_CATALOG_UPDATED_EVENT = 'identity-catalog-updated'

export function dispatchIdentityCatalogUpdated(): void {
  window.dispatchEvent(new Event(IDENTITY_CATALOG_UPDATED_EVENT))
}
