import type { LegalEntityCandidate } from '@/shared/finance/lookup';

export interface LegalEntityFormValue {
  id?: number;
  subject_type: string;
  tax_status: string;
  country: string;
  legal_name: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  inn: string;
  kpp?: string;
  ogrn: string;
  ogrnip: string;
  legal_address: string;
  verification_status?: string;
  verification_reason?: string | null;
  verification_reason_code?: string | null;
  lookup_provider?: string | null;
  lookup_invalid?: boolean;
}

export const EMPTY_LEGAL_ENTITY_FORM: LegalEntityFormValue = {
  subject_type: 'LEGAL_ENTITY',
  tax_status: 'UNKNOWN',
  country: 'RU',
  legal_name: '',
  first_name: '',
  last_name: '',
  middle_name: '',
  inn: '',
  kpp: '',
  ogrn: '',
  ogrnip: '',
  legal_address: '',
};

export type LegalEntityEditState = {
  form: LegalEntityFormValue;
  selected: boolean;
  manual: boolean;
  pendingCandidateId: string | null;
};

export function hasLegalIdentity(value?: Partial<LegalEntityFormValue> | null) {
  return Boolean(value?.inn && (value.legal_name || value.last_name));
}

export function snapshotLegalEntityForm(value?: Partial<LegalEntityFormValue> | null): LegalEntityFormValue {
  return { ...EMPTY_LEGAL_ENTITY_FORM, ...value };
}

export function initialLegalEntityEdit(value?: Partial<LegalEntityFormValue> | null): LegalEntityEditState {
  return {
    form: snapshotLegalEntityForm(value),
    selected: hasLegalIdentity(value),
    manual: false,
    pendingCandidateId: null,
  };
}

export function formFromLookupCandidate(
  candidate: LegalEntityCandidate,
  current: LegalEntityFormValue,
): LegalEntityFormValue {
  return {
    ...EMPTY_LEGAL_ENTITY_FORM,
    country: current.country || 'RU',
    tax_status: current.tax_status || 'UNKNOWN',
    subject_type: candidate.subject_type || current.subject_type,
    legal_name: candidate.display_name || '',
    inn: candidate.inn || '',
    kpp: candidate.kpp || '',
    ogrn: candidate.ogrn || '',
    ogrnip: candidate.ogrnip || '',
    legal_address: candidate.address_summary || '',
    id: candidate.existing_legal_entity_id ?? undefined,
    verification_status: undefined,
    lookup_provider: null,
  };
}

/** Dropdown select updates only local edit state. It never persists. */
export function applyLookupCandidate(
  state: LegalEntityEditState,
  candidate: LegalEntityCandidate,
): LegalEntityEditState {
  return {
    form: formFromLookupCandidate(candidate, state.form),
    selected: true,
    manual: false,
    pendingCandidateId: candidate.candidate_id,
  };
}

export function cancelLegalEntityEdit(saved?: Partial<LegalEntityFormValue> | null): LegalEntityEditState {
  return initialLegalEntityEdit(saved);
}

export function lookupPersistNeeded(state: LegalEntityEditState) {
  return Boolean(state.pendingCandidateId);
}

export function persistLookupRequest(state: LegalEntityEditState) {
  if (!state.pendingCandidateId) return null;
  return { candidate_id: state.pendingCandidateId };
}

export function isLegalEntityEditDirty(
  state: LegalEntityEditState,
  saved?: Partial<LegalEntityFormValue> | null,
) {
  if (state.pendingCandidateId) return true;
  if (state.manual && !hasLegalIdentity(saved)) return true;
  if (state.selected !== hasLegalIdentity(saved)) return true;
  return JSON.stringify(state.form) !== JSON.stringify(snapshotLegalEntityForm(saved));
}
