import { describe, expect, it } from 'vitest';
import { validateReason } from './reason';

describe('validateReason', () => {
  it('rejects an empty reason', () => {
    expect(validateReason('   ')).toBe('Укажите причину');
  });

  it('accepts a non-empty reason', () => {
    expect(validateReason('Broken destination URL')).toBeNull();
  });
});
