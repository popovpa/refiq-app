import { describe, expect, it } from 'vitest';
import { canManuallyReviewLegalEntity, REJECT_REASON_OPTIONS } from './legalEntity';

describe('legal entity admin actions', () => {
  it('shows verify and reject only for pending verification', () => {
    expect(canManuallyReviewLegalEntity('PENDING_VERIFICATION')).toBe(true);
    expect(canManuallyReviewLegalEntity('VERIFIED')).toBe(false);
    expect(canManuallyReviewLegalEntity('REJECTED')).toBe(false);
    expect(canManuallyReviewLegalEntity('DRAFT')).toBe(false);
  });

  it('sends backend enum codes rather than localized labels', () => {
    expect(REJECT_REASON_OPTIONS.map((item) => item.value)).toEqual([
      'INN_NOT_FOUND',
      'ENTITY_INACTIVE',
      'DATA_MISMATCH',
      'UNSUPPORTED_ENTITY_TYPE',
      'INVALID_LEGAL_DATA',
      'OTHER',
    ]);
  });
});
