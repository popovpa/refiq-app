import { VERTICALS } from '@/shared/catalog/categories';
import { TRAFFIC_SOURCES, trafficSourceLabel } from '@/shared/catalog/trafficSources';
import { cn } from '@/shared/utils/cn';

export const OFFER_STATUSES = [
  { key: 'all', label: 'Все' },
  { key: 'active', label: 'Активные' },
  { key: 'draft', label: 'Черновики' },
  { key: 'paused', label: 'Приостановленные' },
  { key: 'archived', label: 'Архивные' },
] as const;

export const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  active: { label: 'Активен', className: 'bg-accent text-primary' },
  draft: { label: 'Черновик', className: 'bg-muted text-muted-foreground' },
  paused: { label: 'Приостановлен', className: 'bg-yellow-50 text-yellow-700' },
  closing: { label: 'Закрывается', className: 'bg-orange-50 text-warning' },
  archived: { label: 'Архивный', className: 'bg-muted text-muted-foreground' },
};

export const ACCESS_OPTIONS = [
  { value: 'open', label: 'Всем партнёрам' },
  { value: 'approval', label: 'После одобрения' },
  { value: 'invite_only', label: 'По приглашению' },
] as const;

export const ACCESS_LABELS: Record<string, string> = {
  open: 'Всем партнёрам',
  approval: 'После одобрения',
  invite_only: 'По приглашению',
};

export const CONVERSION_OPTIONS = [
  { value: 'sale', label: 'Покупка' },
  { value: 'signup', label: 'Регистрация' },
  { value: 'lead', label: 'Заявка' },
  { value: 'application', label: 'Одобренная заявка' },
  { value: 'custom', label: 'Другое' },
] as const;

export const CONVERSION_LABELS: Record<string, string> = Object.fromEntries(
  CONVERSION_OPTIONS.map((item) => [item.value, item.label]),
);

export const CATEGORIES = VERTICALS.map((item) => item.nameRu);

export const CATEGORY_FILTERS = VERTICALS.map((item) => ({ value: item.code, label: item.nameRu }));

export const TRAFFIC_TYPES = TRAFFIC_SOURCES.map((item) => ({ value: item.code, label: item.nameRu }));

export const TRAFFIC_LABELS: Record<string, string> = Object.fromEntries(
  TRAFFIC_TYPES.map((item) => [item.value, item.label]),
);

export const ATTRIBUTION_MODEL_LABEL = 'Последний допустимый партнёрский переход';

export const ATTRIBUTION_MODEL_HINT =
  'Конверсия относится к последнему допустимому переходу партнёра в пределах окна атрибуции.';

export const GEO_OPTIONS = ['RU', 'KZ', 'BY', 'UA', 'US'] as const;

export function statusBadge(status?: string) {
  return STATUS_LABELS[status || 'draft'] || STATUS_LABELS.draft;
}

export function accessLabel(value?: string | null) {
  return ACCESS_LABELS[value || ''] || value || '—';
}

export function conversionLabel(value?: string | null) {
  return CONVERSION_LABELS[value || ''] || value || '—';
}

export function trafficLabel(value: string) {
  return trafficSourceLabel(value) || TRAFFIC_LABELS[value] || value;
}

export function tabClass(active: boolean) {
  return cn(
    'px-3 py-1.5 rounded-[7px] text-xs font-semibold transition-colors',
    active ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
  );
}
