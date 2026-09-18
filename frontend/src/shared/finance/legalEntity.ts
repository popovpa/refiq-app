export interface LegalEntityWriteValue {
  subject_type: string;
  tax_status: string;
  country: string;
  legal_name: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  inn: string;
  ogrn: string;
  ogrnip: string;
  legal_address: string;
  submit: boolean;
}

const STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Черновик',
  PENDING_VERIFICATION: 'На проверке',
  VERIFIED: 'Подтверждено',
  REVIEW_REQUIRED: 'Требуется проверка',
  REJECTED: 'Отклонено',
  BLOCKED: 'Заблокировано',
};

export function verificationStatusLabel(status?: string | null) {
  if (!status) return STATUS_LABELS.DRAFT;
  return STATUS_LABELS[status] || status;
}

export function verificationStatusClass(status?: string | null) {
  const value = status || 'DRAFT';
  if (value === 'VERIFIED') return 'bg-success/10 text-success';
  if (value === 'PENDING_VERIFICATION' || value === 'REVIEW_REQUIRED') return 'bg-orange-50 text-warning';
  if (value === 'REJECTED' || value === 'BLOCKED') return 'bg-red-50 text-destructive';
  return 'bg-muted text-muted-foreground';
}

export type LegalFormContext = 'business' | 'partner';

export const BUSINESS_SUBJECT_TYPE_OPTIONS = [
  { value: 'SOLE_PROPRIETOR', label: 'ИП' },
  { value: 'LEGAL_ENTITY', label: 'Юридическое лицо' },
] as const;

export const PARTNER_SUBJECT_TYPE_OPTIONS = [
  { value: 'INDIVIDUAL', label: 'Самозанятый / НПД' },
  { value: 'SOLE_PROPRIETOR', label: 'ИП' },
  { value: 'LEGAL_ENTITY', label: 'Юридическое лицо' },
] as const;

export const TAX_STATUS_LABELS: Record<string, string> = {
  UNKNOWN: 'Не указан',
  NPD: 'НПД',
  USN: 'УСН',
  OSN: 'ОСН',
  PATENT: 'Патент',
  OTHER: 'Иное',
};

const BUSINESS_TAX_STATUSES = ['UNKNOWN', 'NPD', 'USN', 'OSN', 'PATENT', 'OTHER'] as const;

const PARTNER_TAX_STATUSES: Record<string, readonly string[]> = {
  INDIVIDUAL: ['NPD'],
  SOLE_PROPRIETOR: ['NPD', 'USN', 'OSN', 'PATENT', 'OTHER'],
  LEGAL_ENTITY: ['USN', 'OSN', 'OTHER'],
};

export const UNSUPPORTED_PARTNER_INDIVIDUAL_MESSAGE =
  'Для получения выплат физическое лицо должно иметь статус самозанятого / НПД.';

export function subjectTypeOptions(context: LegalFormContext) {
  return context === 'business' ? BUSINESS_SUBJECT_TYPE_OPTIONS : PARTNER_SUBJECT_TYPE_OPTIONS;
}

export function isUnsupportedPartnerIndividual(subjectType?: string | null, taxStatus?: string | null) {
  return subjectType === 'INDIVIDUAL' && taxStatus !== 'NPD';
}

export function taxStatusOptions(
  context: LegalFormContext,
  subjectType: string,
  currentTax?: string | null,
) {
  if (context !== 'partner') {
    return BUSINESS_TAX_STATUSES.map((value) => ({
      value,
      label: value === 'OTHER' ? 'Другой' : TAX_STATUS_LABELS[value] || value,
    }));
  }
  const allowed = [...(PARTNER_TAX_STATUSES[subjectType] || [])];
  if (subjectType !== 'INDIVIDUAL' && (currentTax === 'UNKNOWN' || !currentTax)) {
    allowed.unshift('UNKNOWN');
  }
  if (currentTax && !allowed.includes(currentTax)) {
    allowed.unshift(currentTax);
  }
  return allowed.map((value) => ({ value, label: TAX_STATUS_LABELS[value] || value }));
}

export function nextTaxStatusOnSubjectChange(
  context: LegalFormContext,
  nextSubject: string,
  currentTax: string,
) {
  if (context !== 'partner') return currentTax;
  if (nextSubject === 'INDIVIDUAL') return 'NPD';
  const allowed = PARTNER_TAX_STATUSES[nextSubject] || [];
  if (allowed.includes(currentTax)) return currentTax;
  return 'UNKNOWN';
}

export function partnerLegalFormError(
  form: { subject_type: string; tax_status: string },
  submit: boolean,
): string | null {
  if (isUnsupportedPartnerIndividual(form.subject_type, form.tax_status)) {
    return UNSUPPORTED_PARTNER_INDIVIDUAL_MESSAGE;
  }
  if (submit && form.subject_type !== 'INDIVIDUAL' && (!form.tax_status || form.tax_status === 'UNKNOWN')) {
    return 'Укажите налоговый статус';
  }
  const allowed = PARTNER_TAX_STATUSES[form.subject_type];
  if (allowed && form.tax_status && form.tax_status !== 'UNKNOWN' && !allowed.includes(form.tax_status)) {
    return 'Недопустимый налоговый статус для выбранного типа';
  }
  return null;
}

export function legalEntityWritePayload(
  form: {
    subject_type: string;
    tax_status: string;
    country: string;
    legal_name: string;
    first_name: string;
    last_name: string;
    middle_name: string;
    inn: string;
    ogrn: string;
    ogrnip: string;
    legal_address: string;
  },
  submit: boolean,
): LegalEntityWriteValue {
  return {
    subject_type: form.subject_type,
    tax_status: form.tax_status,
    country: form.country,
    legal_name: form.legal_name,
    first_name: form.first_name,
    last_name: form.last_name,
    middle_name: form.middle_name,
    inn: form.inn,
    ogrn: form.ogrn,
    ogrnip: form.ogrnip,
    legal_address: form.legal_address,
    submit,
  };
}
