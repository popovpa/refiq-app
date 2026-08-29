export interface LinkStats {
  has_stat_data: boolean;
  clicks: number | null;
  conversions: number | null;
  cr: number | null;
  earned: number | null;
}

export interface PartnerLinkItem {
  id: number | string;
  offer_id: number | string;
  offer_name?: string;
  offer_image_url?: string | null;
  offer_allowed_traffic?: string[];
  offer_forbidden_traffic?: string[];
  name?: string | null;
  short_code: string;
  url: string;
  destination_url?: string | null;
  traffic_source?: string | null;
  notes?: string | null;
  status: string;
  created_at?: string | null;
  stats?: LinkStats | null;
}

export interface LinksSummary {
  active_links: number;
  clicks: number;
  conversions: number;
  earned: number;
}

export interface LinksFilterOptions {
  offers: Array<{ id: number; name: string }>;
  traffic_sources: string[];
}

export interface PartnerLinksResponse {
  items: PartnerLinkItem[];
  total: number;
  page: number;
  per_page: number;
  summary: LinksSummary;
  days: number;
  filter_options: LinksFilterOptions;
}

export const LINKS_PERIOD_DAYS = 7;

export function linkDisplayName(name?: string | null): string {
  return name?.trim() || 'Без названия';
}

export function isUnnamedLink(name?: string | null): boolean {
  return !name?.trim();
}

export function formatLinkStatValue(
  value: number | null | undefined,
  hasData: boolean,
  formatter: (value: number) => string = String,
): string {
  if (!hasData || value === null || value === undefined) return '—';
  return formatter(value);
}

export function formatLinkCr(stats?: LinkStats | null): string {
  if (!stats?.has_stat_data || stats.cr === null || stats.cr === undefined) return '—';
  return `${stats.cr.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}%`;
}

export function formatLinkEarned(stats?: LinkStats | null): string {
  if (!stats?.has_stat_data || stats.earned === null || stats.earned === undefined) return '—';
  return `${stats.earned.toLocaleString('ru-RU')} ₽`;
}

export function linkStatusLabel(status: string): string {
  return status === 'ACTIVE' ? 'Активна' : 'Отключена';
}

export function linkStatusClass(status: string): string {
  return status === 'ACTIVE' ? 'bg-accent text-primary' : 'bg-muted text-muted-foreground';
}

export function formatLinkCreatedAt(value?: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}
