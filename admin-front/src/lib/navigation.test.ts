import { describe, expect, it } from 'vitest';
import { hrefForSearchItem, tracePath } from './navigation';

describe('rqcid navigation', () => {
  it('sends rqcid to the trace screen', () => {
    expect(tracePath('abc123xyz789')).toBe('/trace/abc123xyz789');
    expect(
      hrefForSearchItem({
        type: 'click',
        id: 1,
        title: 'abc123xyz789',
        rqcid: 'abc123xyz789',
        primary_action: 'open_trace',
      }),
    ).toBe('/trace/abc123xyz789');
  });

  it('uses backend href for named entities', () => {
    expect(
      hrefForSearchItem({
        type: 'tracking_link',
        id: 9,
        title: 'k81js92',
        href: '/tracking-links/9',
      }),
    ).toBe('/tracking-links/9');
  });
});
