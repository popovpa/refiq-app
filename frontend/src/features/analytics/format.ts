import { formatMoney, formatNumber } from '@/shared/utils/format';
import type { Metric } from './types';

export function currencySymbol(code?: string | null): string {
  if (!code || code === 'RUB') return '₽';
  return code;
}

export function formatDecimal(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(num)) return '—';
  return num.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatDuration(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const ms = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(ms)) return '—';
  const seconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (minutes <= 0) return `${rest} с`;
  return `${minutes} мин ${rest} с`;
}

export function formatBytes(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const bytes = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(bytes)) return '—';
  if (bytes < 1024) return `${Math.round(bytes)} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${formatDecimal(bytes / (1024 * 1024), 1)} МБ`;
}

export function formatMetric(metric?: Metric | null): string {
  if (!metric || metric.value === null || metric.value === '') return '—';
  if (metric.unit === 'money') return formatMoney(metric.value, currencySymbol(metric.currency));
  if (metric.unit === 'percent') return `${formatDecimal(metric.value, 2)}%`;
  if (metric.unit === 'milliseconds') return formatDuration(metric.value);
  if (metric.unit === 'bytes') return formatBytes(metric.value);
  if (metric.unit === 'score') return formatDecimal(metric.value, 3);
  if (metric.unit === 'ratio') return formatDecimal(metric.value, 2);
  return formatNumber(metric.value);
}

export function formatPercent(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return '—';
  return `${formatDecimal(value, digits)}%`;
}

export function formatChange(value: string | null | undefined): string | undefined {
  if (value === null || value === undefined || value === '') return undefined;
  const num = Number(value);
  if (!Number.isFinite(num)) return undefined;
  const text = `${formatDecimal(Math.abs(num), 1)}%`;
  if (num > 0) return `+${text}`;
  if (num < 0) return `-${text}`;
  return text;
}

export function qualityNote(metric?: Metric | null): string | undefined {
  if (!metric || metric.quality === 'reliable') return undefined;
  if (metric.quality === 'unavailable') return 'Нет данных';
  return 'Неполная выборка';
}

export function formatBucket(value: string): string {
  if (!value) return '';
  if (value.includes('T')) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value.slice(11, 16);
    return date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit' });
  }
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

export function moneyText(value: string | null | undefined, currency?: string | null): string {
  if (value === null || value === undefined || value === '') return '—';
  return formatMoney(value, currencySymbol(currency));
}

const FILTER_API: Record<string, string> = {
  offer: 'offer_id',
  campaign: 'campaign_id',
  partner: 'partner_id',
  site: 'site_id',
  link: 'link_id',
  source: 'traffic_source',
  device: 'device',
  landing: 'landing',
  utm_source: 'utm_source',
  utm_campaign: 'utm_campaign',
};

export function analyticsQuery(
  range: Record<string, string>,
  search: URLSearchParams,
  keys: readonly string[],
): string {
  const params = new URLSearchParams(range);
  for (const key of keys) {
    const value = search.get(key);
    if (value) params.set(FILTER_API[key] || key, value);
  }
  return params.toString();
}
