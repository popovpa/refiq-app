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
  { value: 'open', label: 'Публичный' },
  { value: 'approval', label: 'По одобрению' },
  { value: 'invite_only', label: 'Только по приглашению' },
] as const;

export const ACCESS_LABELS: Record<string, string> = {
  open: 'Публичный',
  approval: 'По одобрению',
  invite_only: 'Только по приглашению',
};

export const CONVERSION_OPTIONS = [
  { value: 'sale', label: 'Покупка' },
  { value: 'signup', label: 'Регистрация' },
  { value: 'lead', label: 'Лид' },
  { value: 'application', label: 'Одобренная заявка' },
  { value: 'custom', label: 'Другое' },
] as const;

export const CONVERSION_LABELS: Record<string, string> = Object.fromEntries(
  CONVERSION_OPTIONS.map((item) => [item.value, item.label]),
);

export const CATEGORIES = ['SaaS', 'Fintech', 'Education', 'E-commerce', 'Marketing', 'Other'] as const;

export const TRAFFIC_TYPES = [
  { value: 'seo', label: 'SEO' },
  { value: 'content', label: 'Контент' },
  { value: 'social', label: 'Социальные сети' },
  { value: 'youtube', label: 'YouTube / Video' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'email', label: 'Email' },
  { value: 'ppc', label: 'PPC' },
] as const;

export const TRAFFIC_LABELS: Record<string, string> = Object.fromEntries(
  TRAFFIC_TYPES.map((item) => [item.value, item.label]),
);

export const ATTRIBUTION_MODEL_LABEL = 'Последний допустимый партнёрский переход';

export const ATTRIBUTION_MODEL_HINT =
  'Конверсия относится к последнему допустимому переходу партнёра в пределах окна атрибуции.';

export const GEO_OPTIONS = ['WW', 'RU', 'KZ', 'BY', 'UA', 'US', 'EU'] as const;

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
  return TRAFFIC_LABELS[value] || value;
}

export function tabClass(active: boolean) {
  return cn(
    'px-3 py-1.5 rounded-[7px] text-xs font-semibold transition-colors',
    active ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
  );
}
