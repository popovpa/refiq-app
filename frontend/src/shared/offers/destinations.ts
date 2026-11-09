export type DestinationType = 'PRODUCT' | 'CATEGORY' | 'LANDING';
export type DestinationStatus = 'active' | 'disabled';

export interface OfferDestinationItem {
  id: number;
  offer_id?: number;
  title: string;
  url: string;
  type: DestinationType;
  image_url?: string | null;
  is_primary: boolean;
  status: DestinationStatus;
  available?: boolean;
  sort_order?: number;
  links_count?: number;
  warning?: string | null;
}

export interface DestinationListResponse {
  items: OfferDestinationItem[];
  total: number;
  page: number;
  per_page: number;
  legacy_product_url?: string | null;
  legacy_skip_reason?: string | null;
}

const TYPE_LABELS: Record<DestinationType, string> = {
  PRODUCT: 'Товар',
  CATEGORY: 'Категория',
  LANDING: 'Посадочная',
};

export function destinationTypeLabel(type?: string | null): string {
  if (type && type in TYPE_LABELS) return TYPE_LABELS[type as DestinationType];
  return 'Страница';
}

export function shortDestinationUrl(url?: string | null): string {
  if (!url) return '—';
  try {
    const parsed = new URL(url);
    const path = `${parsed.pathname}${parsed.search}`;
    const compact = path === '/' ? parsed.host : `${parsed.host}${path}`;
    return compact.length > 72 ? `${compact.slice(0, 69)}…` : compact;
  } catch {
    return url;
  }
}

export function selectedDestinationId(
  destinations: Array<{ id: number; is_primary?: boolean }>,
  options?: { preferredId?: number | null; currentId?: string; fallbackToFirst?: boolean },
): string {
  const items = destinations || [];
  const currentId = options?.currentId || '';
  if (currentId && items.some((item) => String(item.id) === currentId)) return currentId;
  const preferredId = options?.preferredId;
  if (preferredId && items.some((item) => item.id === preferredId)) return String(preferredId);
  if (items.length === 1) return String(items[0].id);
  const primary = items.find((item) => item.is_primary);
  if (primary) return String(primary.id);
  if (options?.fallbackToFirst && items[0]) return String(items[0].id);
  return '';
}

export function trackingLinkName(
  pageTitle: string,
  campaignName: string | null | undefined,
  taken: Iterable<string> = [],
): string {
  const page = pageTitle.trim() || 'Страница';
  const campaign = campaignName?.trim();
  const base = (campaign ? `${page} · ${campaign}` : page).slice(0, 255);
  const used = new Set(Array.from(taken, (item) => item.trim()).filter(Boolean));
  if (!used.has(base)) return base;
  let index = 2;
  while (used.has(`${base} ${index}`.slice(0, 255))) index += 1;
  const suffix = ` ${index}`;
  return `${base.slice(0, 255 - suffix.length)}${suffix}`;
}

export function legacySkipMessage(reason?: string | null): string | null {
  if (!reason || reason === 'missing_url') return null;
  if (reason === 'COMPLIANCE_VERTICAL_FORBIDDEN') {
    return 'Эту страницу нельзя опубликовать: gambling запрещён.';
  }
  if (reason === 'COMPLIANCE_RESTRICTED_REQUIRED') {
    return 'Ставки публикуются только в режиме одобрения или приглашения.';
  }
  if (reason === 'DESTINATION_HTTPS_REQUIRED') return 'Основной URL не опубликован: для страницы нужен HTTPS.';
  return 'Текущий URL продукта не опубликован как посадочная страница.';
}
