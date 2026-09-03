import { describe, expect, it } from 'vitest';
import {
  OWN_OFFER_PROMOTE_PENDING_LABEL,
  OWN_OFFER_PROMOTE_TOAST,
  canStartOwnOfferPromote,
  ownOfferPromoteContext,
  ownOfferPromotePath,
} from './promoteOwnOffer';

describe('promoteOwnOffer', () => {
  it('opens the owning business offer on the promotion tab with create-link intent', () => {
    expect(ownOfferPromotePath(42)).toBe('/business/offers/42?tab=promotion&createLink=1');
    expect(ownOfferPromoteContext(42)).toEqual({ role: 'business', offer_id: 42 });
  });

  it('explains the partner-to-business switch without technical terms', () => {
    expect(OWN_OFFER_PROMOTE_TOAST).toContain('режим бизнеса');
    expect(OWN_OFFER_PROMOTE_TOAST).toContain('без партнёрской комиссии');
    expect(OWN_OFFER_PROMOTE_PENDING_LABEL).toBe('Переходим в режим бизнеса…');
  });

  it('blocks a second transition while one is already pending', () => {
    expect(canStartOwnOfferPromote(false)).toBe(true);
    expect(canStartOwnOfferPromote(true)).toBe(false);
  });
});
