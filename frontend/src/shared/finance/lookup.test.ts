import { describe, expect, it } from 'vitest';
import {
  lookupEnabledForSubject,
  registryIdLine,
  shouldSearch,
  subjectTypeShortLabel,
  usedInLabel,
} from './lookup';

describe('legal entity lookup ui', () => {
  it('starts search after 3 characters or a complete INN', () => {
    expect(shouldSearch('')).toBe(false);
    expect(shouldSearch('ро')).toBe(false);
    expect(shouldSearch('ром')).toBe(true);
    expect(shouldSearch('7701234567')).toBe(true);
    expect(shouldSearch('123456789012')).toBe(true);
  });

  it('does not enable DaData party search for NPD individuals', () => {
    expect(lookupEnabledForSubject('partner', 'INDIVIDUAL')).toBe(false);
    expect(lookupEnabledForSubject('partner', 'SOLE_PROPRIETOR')).toBe(true);
    expect(lookupEnabledForSubject('business', 'LEGAL_ENTITY')).toBe(true);
    expect(lookupEnabledForSubject('business', 'INDIVIDUAL')).toBe(false);
  });

  it('formats compact result lines and reuse labels', () => {
    expect(subjectTypeShortLabel('LEGAL_ENTITY')).toBe('Юрлицо');
    expect(registryIdLine({ inn: '7701234567', ogrn: '123', subject_type: 'LEGAL_ENTITY' })).toContain('ИНН');
    expect(usedInLabel(['business'])).toBe('Уже используется в режиме «Бизнес»');
  });
});
