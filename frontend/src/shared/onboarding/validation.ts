import type { OrgOnboardingForm } from '@/shared/onboarding/flow';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_RE = /^https?:\/\/.+\..+/i;

export type OrgFormErrors = Partial<Record<keyof OrgOnboardingForm, string>>;

export function validateInn(value: string, subjectType: string): string | null {
  const digits = value.replace(/\D/g, '');
  if (!digits) return 'Укажите ИНН';
  const length = subjectType === 'LEGAL_ENTITY' ? 10 : 12;
  if (digits.length !== length) return `ИНН должен содержать ${length} цифр`;
  return null;
}

export function validateOgrn(value: string, subjectType: string): string | null {
  const digits = value.replace(/\D/g, '');
  if (subjectType === 'LEGAL_ENTITY') {
    if (!digits) return 'Укажите ОГРН';
    if (digits.length !== 13) return 'ОГРН должен содержать 13 цифр';
  }
  if (subjectType === 'SOLE_PROPRIETOR') {
    if (!digits) return 'Укажите ОГРНИП';
    if (digits.length !== 15) return 'ОГРНИП должен содержать 15 цифр';
  }
  return null;
}

export function validateOrgOnboardingForm(
  form: OrgOnboardingForm,
  options: { context: 'business' | 'partner'; selfEmployed?: boolean },
): OrgFormErrors {
  const { context, selfEmployed = false } = options;
  const errors: OrgFormErrors = {};
  if (selfEmployed) {
    if (!form.contact_name.trim()) errors.contact_name = 'Укажите ФИО';
    const inn = validateInn(form.inn, 'INDIVIDUAL');
    if (inn) errors.inn = inn;
    if (!form.country) errors.country = 'Выберите страну';
    if (!form.work_email.trim()) errors.work_email = 'Укажите email';
    else if (!EMAIL_RE.test(form.work_email.trim())) errors.work_email = 'Некорректный email';
    if (form.phone.trim() && form.phone.trim().length < 5) errors.phone = 'Слишком короткий телефон';
    return errors;
  }
  if (!form.legal_name.trim() && !(form.last_name && form.first_name)) {
    errors.legal_name = 'Укажите наименование';
  }
  const inn = validateInn(form.inn, form.subject_type);
  if (inn) errors.inn = inn;
  const ogrn = validateOgrn(form.subject_type === 'SOLE_PROPRIETOR' ? form.ogrnip : form.ogrn, form.subject_type);
  if (ogrn) {
    if (form.subject_type === 'SOLE_PROPRIETOR') errors.ogrnip = ogrn;
    else errors.ogrn = ogrn;
  }
  if (!form.country) errors.country = 'Выберите страну';
  if (form.subject_type === 'LEGAL_ENTITY' && !form.legal_address.trim()) {
    errors.legal_address = 'Укажите юридический адрес';
  }
  if (!form.contact_name.trim()) errors.contact_name = 'Укажите ФИО контактного лица';
  if (!form.work_email.trim()) errors.work_email = context === 'business' ? 'Укажите рабочий email' : 'Укажите email';
  else if (!EMAIL_RE.test(form.work_email.trim())) errors.work_email = 'Некорректный email';
  if (!form.phone.trim()) errors.phone = 'Укажите телефон';
  else if (form.phone.trim().length < 5) errors.phone = 'Слишком короткий телефон';
  if (context === 'business' && form.website.trim() && !URL_RE.test(form.website.trim())) {
    errors.website = 'Укажите корректный URL, например https://example.com';
  }
  return errors;
}
