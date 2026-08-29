export interface BusinessLookupItem {
  id: number | string;
  name: string;
}

export function businessFilterTriggerLabel(name?: string | null, selectedId?: string) {
  const value = name?.trim();
  if (value) return value;
  if (selectedId) return '…';
  return 'Все бизнесы';
}

export const BUSINESS_FILTER_DEBOUNCE_MS = 300;
