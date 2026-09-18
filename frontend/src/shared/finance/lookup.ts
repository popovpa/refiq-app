export interface LegalEntityCandidate {
  candidate_id: string;
  display_name: string;
  subject_type: string;
  inn: string;
  kpp?: string | null;
  ogrn?: string | null;
  ogrnip?: string | null;
  opf?: string | null;
  region?: string | null;
  address_summary?: string | null;
  status: string;
  existing_legal_entity_id?: number | null;
  reuse_available: boolean;
  verification_status?: string | null;
  used_in?: string[];
}

export type LookupContext = 'business' | 'partner';

export function shouldSearch(query: string): boolean {
  const value = query.trim();
  if (!value) return false;
  const digits = value.replace(/\D/g, '');
  if (digits.length === 10 || digits.length === 12) return true;
  return value.length >= 3;
}

export function subjectTypeShortLabel(subjectType?: string | null) {
  if (subjectType === 'LEGAL_ENTITY') return 'Юрлицо';
  if (subjectType === 'SOLE_PROPRIETOR') return 'ИП';
  if (subjectType === 'INDIVIDUAL') return 'Самозанятый';
  return subjectType || '';
}

export function usedInLabel(usedIn?: string[]) {
  if (!usedIn?.length) return null;
  if (usedIn.includes('business') && usedIn.includes('partner')) {
    return 'Уже используется в режимах «Бизнес» и «Партнёр»';
  }
  if (usedIn.includes('business')) return 'Уже используется в режиме «Бизнес»';
  if (usedIn.includes('partner')) return 'Уже используется в режиме «Партнёр»';
  return null;
}

export function registryIdLine(candidate: Pick<LegalEntityCandidate, 'inn' | 'ogrn' | 'ogrnip' | 'subject_type'>) {
  const parts = [`ИНН ${candidate.inn}`];
  if (candidate.subject_type === 'SOLE_PROPRIETOR' && candidate.ogrnip) {
    parts.push(`ОГРНИП ${candidate.ogrnip}`);
  } else if (candidate.ogrn) {
    parts.push(`ОГРН ${candidate.ogrn}`);
  }
  return parts.join(' · ');
}

export function lookupEnabledForSubject(context: LookupContext, subjectType: string) {
  if (context === 'business') {
    return subjectType === 'LEGAL_ENTITY' || subjectType === 'SOLE_PROPRIETOR';
  }
  return subjectType === 'LEGAL_ENTITY' || subjectType === 'SOLE_PROPRIETOR';
}
