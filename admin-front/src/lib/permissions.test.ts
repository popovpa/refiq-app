import { describe, expect, it } from 'vitest';
import { hasPermission, ADMIN_FINANCE, ADMIN_READ, ADMIN_SUPER } from './permissions';

describe('hasPermission', () => {
  it('grants an exact permission', () => {
    expect(hasPermission([ADMIN_READ], ADMIN_READ)).toBe(true);
    expect(hasPermission([ADMIN_READ], ADMIN_FINANCE)).toBe(false);
  });

  it('lets ADMIN_SUPER pass every check', () => {
    expect(hasPermission([ADMIN_SUPER], ADMIN_FINANCE)).toBe(true);
  });
});
