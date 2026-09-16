import { describe, expect, it } from 'vitest';
import { partnerDisplayName } from './displayName';

describe('partnerDisplayName', () => {
  it('keeps a safe nickname', () => {
    expect(partnerDisplayName('Мария', 12)).toBe('Мария');
  });

  it('does not show an email as a name', () => {
    expect(partnerDisplayName('hidden@example.com', 44)).toBe('Партнёр #44');
  });

  it('falls back to a neutral id when the name is missing', () => {
    expect(partnerDisplayName(null, 7)).toBe('Партнёр #7');
    expect(partnerDisplayName('   ')).toBe('');
    expect(partnerDisplayName('hidden@example.com')).toBe('Партнёр');
  });
});
