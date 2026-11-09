import { describe, expect, it } from 'vitest';
import {
  destinationTypeLabel,
  legacySkipMessage,
  shortDestinationUrl,
  selectedDestinationId,
  trackingLinkName,
} from '@/shared/offers/destinations';

describe('offer destinations', () => {
  it('keeps product query strings visible in the short url', () => {
    expect(shortDestinationUrl('https://demo-clickstream-001.refiq.ru/product.html?id=nova-max')).toContain(
      'id=nova-max',
    );
    expect(shortDestinationUrl('https://demo-clickstream-001.refiq.ru/product.html?id=pulse-se')).not.toContain(
      'nova-max',
    );
  });

  it('labels page types without turning them into commission rules', () => {
    expect(destinationTypeLabel('PRODUCT')).toBe('Товар');
    expect(destinationTypeLabel('CATEGORY')).toBe('Категория');
    expect(destinationTypeLabel('LANDING')).toBe('Посадочная');
  });

  it('selects the only page, the primary page, or nothing', () => {
    const pages = [
      { id: 1, is_primary: false },
      { id: 2, is_primary: true },
    ];
    expect(selectedDestinationId([{ id: 7, is_primary: false }])).toBe('7');
    expect(selectedDestinationId(pages)).toBe('2');
    expect(selectedDestinationId(pages, { preferredId: 1 })).toBe('1');
    expect(selectedDestinationId([{ id: 3, is_primary: false }, { id: 4, is_primary: false }])).toBe('');
    expect(selectedDestinationId(pages, { currentId: '1' })).toBe('1');
  });

  it('builds a link name from the page and an optional campaign', () => {
    expect(trackingLinkName('Nova Phone X1', 'VK')).toBe('Nova Phone X1 · VK');
    expect(trackingLinkName('Nova Phone X1', null)).toBe('Nova Phone X1');
    expect(trackingLinkName('Nova Phone X1', '  ')).toBe('Nova Phone X1');
    expect(trackingLinkName('Nova Phone X1', 'VK', ['Nova Phone X1 · VK'])).toBe('Nova Phone X1 · VK 2');
    expect(trackingLinkName('Nova Phone X1', null, ['Nova Phone X1', 'Nova Phone X1 2'])).toBe('Nova Phone X1 3');
  });

  it('explains why a legacy url was not published', () => {
    expect(legacySkipMessage('COMPLIANCE_VERTICAL_FORBIDDEN')).toMatch(/gambling/i);
    expect(legacySkipMessage('missing_url')).toBeNull();
  });
});
