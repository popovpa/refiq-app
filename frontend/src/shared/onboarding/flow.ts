import type { LegalEntityCandidate } from '@/shared/finance/lookup';
import { formFromLookupCandidate, type LegalEntityFormValue } from '@/shared/finance/legalEntityEdit';

export type OnboardingMode = 'choose' | 'business' | 'partner';
export type PartnerKind = 'INDIVIDUAL' | 'SOLE_PROPRIETOR' | 'LEGAL_ENTITY';
export type OnboardingStep = 'choose' | 'partner-type' | 'search' | 'form' | 'self-employed';

export type OrgOnboardingForm = LegalEntityFormValue & {
  contact_name: string;
  job_title: string;
  work_email: string;
  phone: string;
  website: string;
  city: string;
  candidate_id: string | null;
};

export function emptyOrgForm(defaults?: Partial<OrgOnboardingForm>): OrgOnboardingForm {
  return {
    subject_type: defaults?.subject_type || 'LEGAL_ENTITY',
    tax_status: defaults?.tax_status || 'UNKNOWN',
    country: defaults?.country || 'RU',
    legal_name: '',
    first_name: '',
    last_name: '',
    middle_name: '',
    inn: '',
    kpp: '',
    ogrn: '',
    ogrnip: '',
    legal_address: '',
    contact_name: defaults?.contact_name || '',
    job_title: defaults?.job_title || '',
    work_email: defaults?.work_email || '',
    phone: defaults?.phone || '',
    website: defaults?.website || '',
    city: defaults?.city || '',
    candidate_id: null,
    ...defaults,
  };
}

export function applyCandidateToOrgForm(
  form: OrgOnboardingForm,
  candidate: LegalEntityCandidate,
): OrgOnboardingForm {
  const legal = formFromLookupCandidate(candidate, form);
  const contact =
    form.contact_name ||
    [legal.last_name, legal.first_name, legal.middle_name].filter(Boolean).join(' ') ||
    '';
  return {
    ...form,
    ...legal,
    candidate_id: candidate.candidate_id,
    contact_name: contact,
  };
}

export function orgFormHasEdits(current: OrgOnboardingForm, snapshot: OrgOnboardingForm) {
  return JSON.stringify(current) !== JSON.stringify(snapshot);
}

export function splitFio(value: string) {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return { first_name: '', last_name: '', middle_name: '' };
  if (parts.length === 1) return { first_name: parts[0], last_name: '', middle_name: '' };
  if (parts.length === 2) return { last_name: parts[0], first_name: parts[1], middle_name: '' };
  return { last_name: parts[0], first_name: parts[1], middle_name: parts.slice(2).join(' ') };
}

export function nextOnboardingStep(mode: OnboardingMode, partnerKind?: PartnerKind | null): OnboardingStep {
  if (mode === 'choose') return 'choose';
  if (mode === 'business') return 'search';
  if (!partnerKind) return 'partner-type';
  if (partnerKind === 'INDIVIDUAL') return 'self-employed';
  return 'search';
}
