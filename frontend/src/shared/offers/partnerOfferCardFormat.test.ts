import { describe, expect, it } from 'vitest';
import {
  OFFER_CARD_TITLE_MAX,
  formatCommissionContext,
  formatOfferGeo,
  offerCardAccessLabel,
  offerCardCategoryName,
  offerCardMetricValue,
  offerCardTitle,
} from '@/shared/offers/partnerOfferCardFormat';

describe('partner offer card format', () => {
  it('keeps titles within 80 characters and two-line friendly length', () => {
    expect(OFFER_CARD_TITLE_MAX).toBe(80);
    expect(offerCardTitle('Python Academy Pro')).toBe('Python Academy Pro');
    const long = 'A'.repeat(90);
    expect(offerCardTitle(long).length).toBeLessThanOrEqual(81);
    expect(offerCardTitle(long).endsWith('…')).toBe(true);
  });

  it('shows only the category name, not vertical → category', () => {
    expect(
      offerCardCategoryName({
        category: 'ONLINE_COURSES',
        category_code: 'ONLINE_COURSES',
        category_name: 'Онлайн-курсы',
      }),
    ).toBe('Онлайн-курсы');
    expect(offerCardCategoryName({ category: 'ONLINE_COURSES' })).toBe('Онлайн-курсы');
    expect(offerCardCategoryName({ category: 'ONLINE_COURSES' })).not.toContain('→');
  });

  it('formats geo, access, metrics and commission captions for the card', () => {
    expect(formatOfferGeo('WW')).toBe('Весь мир');
    expect(formatOfferGeo('RU, KZ')).toBe('RU, KZ');
    expect(formatOfferGeo('AI,AF,AD')).toBe('AI, AF, AD');
    expect(offerCardAccessLabel('approval')).toBe('После одобрения');
    expect(offerCardAccessLabel('open')).toBe('Публичный');
    expect(offerCardAccessLabel('invite_only')).toBe('По приглашению');
    expect(offerCardMetricValue('—')).toBe('-');
    expect(offerCardMetricValue('8,4%')).toBe('8,4%');
    expect(formatCommissionContext('sale', { type: 'percent', value: 10, currency: 'RUB' })).toBe('с продажи');
    expect(formatCommissionContext('lead', { type: 'fixed', value: 5000, currency: 'RUB' })).toBe(
      'за подтвержденный лид',
    );
  });
});
