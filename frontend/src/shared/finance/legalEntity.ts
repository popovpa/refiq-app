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
