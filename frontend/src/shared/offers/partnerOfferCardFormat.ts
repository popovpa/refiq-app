import type { CommissionRule, OfferListItem } from '@/shared/offers/types';
import { conversionLabel } from '@/shared/offers/labels';
import { formatNumber } from '@/shared/utils/format';

const CONVERSION_CONTEXT: Record<string, { percent: string; fixed: string }> = {
  sale: { percent: 'с покупки', fixed: 'за покупку' },
  signup: { percent: 'с регистрации', fixed: 'за регистрацию' },
  lead: { percent: 'с одобренного лида', fixed: 'за одобренный лид' },
  application: { percent: 'с одобренной заявки', fixed: 'за одобренную заявку' },
  custom: { percent: 'с конверсии', fixed: 'за конверсию' },
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
