import { describe, expect, it } from 'vitest';
import { PARTNER_ONBOARDING_TYPES } from '@/shared/onboarding/constants';
import {
  applyCandidateToOrgForm,
  emptyOrgForm,
  nextOnboardingStep,
  orgFormHasEdits,
  splitFio,
} from '@/shared/onboarding/flow';
import { validateOrgOnboardingForm } from '@/shared/onboarding/validation';
import type { LegalEntityCandidate } from '@/shared/finance/lookup';

const candidate = (id: string, name: string, inn: string): LegalEntityCandidate => ({
  candidate_id: id,
  display_name: name,
  subject_type: 'LEGAL_ENTITY',
  inn,
  ogrn: '1234567890123',
  address_summary: 'Москва',
  status: 'ACTIVE',
  reuse_available: false,
});

describe('onboarding flow', () => {
  it('does not offer ordinary individual as a partner type', () => {
    const labels = PARTNER_ONBOARDING_TYPES.map((item) => item.label).join(' ');
    const values = PARTNER_ONBOARDING_TYPES.map((item) => item.value);
    expect(labels).toContain('Самозанятый');
    expect(labels).not.toContain('Физическое лицо');
    expect(values).toEqual(['INDIVIDUAL', 'SOLE_PROPRIETOR', 'LEGAL_ENTITY']);
    expect(values).not.toContain('PERSON');
    expect(values).not.toContain('PHYSICAL_PERSON');
  });

  it('routes business to search and self-employed to a short form', () => {
    expect(nextOnboardingStep('business')).toBe('search');
    expect(nextOnboardingStep('partner')).toBe('partner-type');
    expect(nextOnboardingStep('partner', 'INDIVIDUAL')).toBe('self-employed');
    expect(nextOnboardingStep('partner', 'SOLE_PROPRIETOR')).toBe('search');
    expect(nextOnboardingStep('partner', 'LEGAL_ENTITY')).toBe('search');
  });

  it('applies a search candidate locally without persisting', () => {
    const form = emptyOrgForm({ work_email: 'a@example.com' });
    const next = applyCandidateToOrgForm(form, candidate('a', 'ООО Ромашка', '7701234567'));
    expect(next.legal_name).toBe('ООО Ромашка');
    expect(next.inn).toBe('7701234567');
    expect(next.candidate_id).toBe('a');
    expect(form.candidate_id).toBeNull();
  });

  it('keeps only the last selected candidate before save', () => {
    const first = applyCandidateToOrgForm(emptyOrgForm(), candidate('a', 'ООО А', '7701234567'));
    const second = applyCandidateToOrgForm(first, candidate('b', 'ООО Б', '7707654321'));
    expect(second.candidate_id).toBe('b');
    expect(second.legal_name).toBe('ООО Б');
    expect(second.inn).toBe('7707654321');
  });

  it('detects unsaved edits before searching another organization', () => {
    const snapshot = applyCandidateToOrgForm(emptyOrgForm(), candidate('a', 'ООО Ромашка', '7701234567'));
    const edited = { ...snapshot, legal_address: 'другой адрес' };
    expect(orgFormHasEdits(edited, snapshot)).toBe(true);
    expect(orgFormHasEdits(snapshot, snapshot)).toBe(false);
  });

  it('validates inn / ogrn / email and allows a self-employed form without ogrn', () => {
    const org = emptyOrgForm({
      legal_name: 'ООО Ромашка',
      inn: '123',
      ogrn: '1',
      contact_name: 'Иван Иванов',
      work_email: 'bad',
      phone: '1',
    });
    const errors = validateOrgOnboardingForm(org, { context: 'business' });
    expect(errors.inn).toMatch(/10 цифр/);
    expect(errors.ogrn).toMatch(/13 цифр/);
    expect(errors.work_email).toMatch(/email/i);
    expect(errors.phone).toMatch(/телефон/i);

    const npd = emptyOrgForm({
      subject_type: 'INDIVIDUAL',
      contact_name: 'Иван Иванов',
      inn: '123456789012',
      work_email: 'npd@example.com',
      country: 'RU',
    });
    expect(validateOrgOnboardingForm(npd, { context: 'partner', selfEmployed: true })).toEqual({});
  });

  it('splits FIO for a self-employed partner', () => {
    expect(splitFio('Иванов Иван Иванович')).toEqual({
      last_name: 'Иванов',
      first_name: 'Иван',
      middle_name: 'Иванович',
    });
  });
});
