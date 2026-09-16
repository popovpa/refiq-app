import { findCategory, resolveCategoryCode } from '@/shared/catalog/categories';
import type { CommissionRule, OfferListItem } from '@/shared/offers/types';
import { conversionLabel } from '@/shared/offers/labels';
import { formatNumber } from '@/shared/utils/format';

export const OFFER_CARD_TITLE_MAX = 80;
export const OFFER_CARD_METRIC_EMPTY = '-';

const CONVERSION_CONTEXT: Record<string, { percent: string; fixed: string }> = {
  sale: { percent: 'с продажи', fixed: 'за покупку' },
  signup: { percent: 'с регистрации', fixed: 'за регистрацию' },
  lead: { percent: 'с заявки', fixed: 'за подтвержденный лид' },
  application: { percent: 'с одобренной заявки', fixed: 'за одобренную заявку' },
  custom: { percent: 'с конверсии', fixed: 'за конверсию' },
};

const CARD_ACCESS_LABEL: Record<string, string> = {
  open: 'Публичный',
  approval: 'После одобрения',
  invite_only: 'По приглашению',
};

export const ACCESS_BADGE: Record<string, { label: string; className: string }> = {
  open: { label: 'Публичный', className: 'bg-accent text-primary' },
  approval: { label: 'По одобрению', className: 'bg-yellow-50 text-yellow-700' },
  invite_only: { label: 'Только по приглашению', className: 'bg-muted text-muted-foreground' },
};

const INSUFFICIENT_STATS_TITLE = 'Недостаточно данных для расчёта';

export function formatCommissionPrimary(rule?: CommissionRule | null): string {
  if (!rule || rule.value === null || rule.value === undefined) {
    return '—';
  }
  if (rule.type === 'percent') {
    return `${formatNumber(rule.value)}%`;
  }
  const currency = !rule.currency || rule.currency === 'RUB' ? '₽' : rule.currency;
  return `${formatNumber(rule.value)} ${currency}`;
}

export function formatCommissionContext(
  conversionType: string | null | undefined,
  rule?: CommissionRule | null,
): string {
  if (!rule || rule.value === null || rule.value === undefined) {
    return conversionLabel(conversionType);
  }
  const phrases = CONVERSION_CONTEXT[conversionType || ''] || CONVERSION_CONTEXT.custom;
  return rule.type === 'percent' ? phrases.percent : phrases.fixed;
}

export function hasOfferStatData(offer: Pick<OfferListItem, 'clicks'>): boolean {
  return (offer.clicks ?? 0) > 0;
}

export function formatOfferEpc(offer: OfferListItem): { value: string; title?: string } {
  if (!hasOfferStatData(offer)) {
    return { value: '—', title: INSUFFICIENT_STATS_TITLE };
  }
  return { value: `${formatNumber(offer.epc)} ₽` };
}

export function formatOfferCr(offer: OfferListItem): { value: string; title?: string } {
  if (!hasOfferStatData(offer)) {
    return { value: '—', title: INSUFFICIENT_STATS_TITLE };
  }
  return { value: `${formatNumber(offer.cr)}%` };
}

export function accessBadge(accessPolicy: string) {
  return ACCESS_BADGE[accessPolicy] || {
    label: accessPolicy,
    className: 'bg-muted text-muted-foreground',
  };
}

export function offerCardTitle(name?: string | null): string {
  const value = (name || '').trim();
  if (value.length <= OFFER_CARD_TITLE_MAX) return value;
  return `${value.slice(0, OFFER_CARD_TITLE_MAX).trimEnd()}…`;
}

export function offerCardCategoryName(offer: Pick<OfferListItem, 'category' | 'category_code' | 'category_name'>): string | null {
  if (offer.category_name?.trim()) return offer.category_name.trim();
  const code = resolveCategoryCode(offer.category_code || offer.category) || offer.category;
  return findCategory(code)?.nameRu || null;
}

export function formatOfferGeo(geo?: string | null): string {
  const value = (geo || '').trim();
  if (!value || value === 'WW' || value.toLowerCase() === 'worldwide') return 'Весь мир';
  return value.replace(/,\s*/g, ', ');
}

export function offerCardAccessLabel(accessPolicy?: string | null): string {
  if (!accessPolicy) return OFFER_CARD_METRIC_EMPTY;
  return CARD_ACCESS_LABEL[accessPolicy] || accessPolicy;
}

export function offerCardMetricValue(value?: string | null): string {
  if (!value || value === '—') return OFFER_CARD_METRIC_EMPTY;
  return value;
}

export function pluralize(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

export function formatLinksCount(count: number): string {
  return `${formatNumber(count)} ${pluralize(count, 'ссылка', 'ссылки', 'ссылок')}`;
}

export function formatPartnerPromotionStats(offer: OfferListItem): { value: string; title?: string } {
  const clicks = offer.partner_clicks ?? 0;
  if (clicks <= 0) {
    return { value: '—', title: INSUFFICIENT_STATS_TITLE };
  }
  const conversions = offer.partner_conversions ?? 0;
  return {
    value: `${formatNumber(clicks)} ${pluralize(clicks, 'клик', 'клика', 'кликов')} · ${formatNumber(conversions)} ${pluralize(conversions, 'конверсия', 'конверсии', 'конверсий')} · CR ${formatNumber(offer.partner_cr)}%`,
  };
}
