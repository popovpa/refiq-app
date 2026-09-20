import { describe, expect, it } from 'vitest';
import type { LegalEntityCandidate } from '@/shared/finance/lookup';
import {
  applyLookupCandidate,
  cancelLegalEntityEdit,
  initialLegalEntityEdit,
  lookupPersistNeeded,
  persistLookupRequest,
} from '@/shared/finance/legalEntityEdit';

const SAVED = {
  id: 12,
  subject_type: 'LEGAL_ENTITY',
  tax_status: 'USN',
  country: 'RU',
  legal_name: 'ООО Исходная',
  first_name: '',
  last_name: '',
  middle_name: '',
  inn: '7700000000',
  ogrn: '1027700000000',
  ogrnip: '',
  legal_address: 'Москва, исходный адрес',
  verification_status: 'VERIFIED',
};

function candidate(overrides: Partial<LegalEntityCandidate> = {}): LegalEntityCandidate {
  return {
    candidate_id: 'candidate-a',
    display_name: 'ООО Ромашка',
    subject_type: 'LEGAL_ENTITY',
    inn: '7701234567',
    kpp: '770101001',
    ogrn: '1234567890123',
    address_summary: 'г Москва',
    status: 'ACTIVE',
    reuse_available: false,
    ...overrides,
  };
}

describe('legal entity edit: select is not save', () => {
  it('keeps backend state unchanged after a dropdown select', () => {
    const saved = initialLegalEntityEdit(SAVED);
    const next = applyLookupCandidate(saved, candidate());

    expect(next.form.legal_name).toBe('ООО Ромашка');
    expect(next.form.inn).toBe('7701234567');
    expect(next.pendingCandidateId).toBe('candidate-a');
    expect(lookupPersistNeeded(next)).toBe(true);
    expect(saved.form.inn).toBe(SAVED.inn);
    expect(saved.pendingCandidateId).toBeNull();
    expect(lookupPersistNeeded(saved)).toBe(false);
  });

  it('restores the saved LegalEntity after select + Cancel', () => {
    const selected = applyLookupCandidate(initialLegalEntityEdit(SAVED), candidate());
    const cancelled = cancelLegalEntityEdit(SAVED);

    expect(cancelled.form.legal_name).toBe(SAVED.legal_name);
    expect(cancelled.form.inn).toBe(SAVED.inn);
    expect(cancelled.form.id).toBe(SAVED.id);
    expect(cancelled.pendingCandidateId).toBeNull();
    expect(lookupPersistNeeded(cancelled)).toBe(false);
    expect(lookupPersistNeeded(selected)).toBe(true);
  });

  it('persists only the last selected candidate before Save', () => {
    const first = applyLookupCandidate(initialLegalEntityEdit(SAVED), candidate());
    const second = applyLookupCandidate(
      first,
      candidate({
        candidate_id: 'candidate-b',
        display_name: 'ООО Васильёк',
        inn: '7707654321',
      }),
    );

    expect(first.pendingCandidateId).toBe('candidate-a');
    expect(second.pendingCandidateId).toBe('candidate-b');
    expect(second.form.legal_name).toBe('ООО Васильёк');
    expect(second.form.inn).toBe('7707654321');
    expect(lookupPersistNeeded(second)).toBe(true);
    expect(second.pendingCandidateId).not.toBe(first.pendingCandidateId);
  });

  it('saves only after an explicit Save of the pending candidate', () => {
    const selected = applyLookupCandidate(initialLegalEntityEdit(SAVED), candidate());
    expect(persistLookupRequest(selected)).toEqual({ candidate_id: 'candidate-a' });
    expect(persistLookupRequest(cancelLegalEntityEdit(SAVED))).toBeNull();
    expect(persistLookupRequest(initialLegalEntityEdit(SAVED))).toBeNull();
  });
});
