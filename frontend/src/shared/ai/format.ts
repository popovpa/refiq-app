import {
  ACCESS_LABELS,
  CONVERSION_LABELS,
  TRAFFIC_LABELS,
  trafficLabel,
} from '@/shared/offers/labels';

export const OFFER_AI_FIELD_LABELS: Record<string, string> = {
  name: 'Название',
  description: 'Описание',
  category: 'Категория',
  geo: 'GEO',
  partner_notes: 'Инструкции для партнёров',
  allowed_traffic: 'Разрешённый трафик',
  forbidden_traffic: 'Запрещённый трафик',
  product_url: 'Сайт продукта',
  conversion_type: 'Тип conversion goal',
  commission_type: 'Модель комиссии',
  commission_value: 'Размер комиссии',
  commission_currency: 'Валюта',
  attribution_window_days: 'Окно атрибуции',
  access_policy: 'Тип доступа',
};

export function formatOfferAiValue(field: string, value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => trafficLabel(String(item))).join(', ') || '—';
  }
  if (value == null || value === '') return '—';
  const text = String(value);
  if (field === 'conversion_type') return CONVERSION_LABELS[text] || text;
  if (field === 'access_policy') return ACCESS_LABELS[text] || text;
  if (field === 'commission_type') return text === 'percent' ? 'Процент' : text === 'fixed' ? 'Фиксированная сумма' : text;
  if (field === 'allowed_traffic' || field === 'forbidden_traffic') return TRAFFIC_LABELS[text] || text;
  return text;
}
