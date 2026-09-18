import { describe, expect, it } from 'vitest';
import {
  isUnsupportedPartnerIndividual,
  legalEntityWritePayload,
  nextTaxStatusOnSubjectChange,
  partnerLegalFormError,
  subjectTypeOptions,
  taxStatusOptions,
  verificationStatusClass,
  verificationStatusLabel,
} from './legalEntity';

describe('legal entity user payload', () => {
  it('does not send verification status from the cabinet form', () => {
    const payload = legalEntityWritePayload(
      {
        subject_type: 'LEGAL_ENTITY',
        tax_status: 'USN',
        country: 'RU',
        legal_name: 'ООО Тест',
        first_name: '',
        last_name: '',
        middle_name: '',
        inn: '1234567890',
        ogrn: '1234567890123',
        ogrnip: '',
        legal_address: 'Москва',
      },
      true,
    );
    expect(payload).not.toHaveProperty('verification_status');
    expect(payload.submit).toBe(true);
  });

  it('labels rejected and pending statuses for the user', () => {
    expect(verificationStatusLabel('REJECTED')).toBe('Отклонено');
    expect(verificationStatusLabel('PENDING_VERIFICATION')).toBe('На проверке');
    expect(verificationStatusLabel('VERIFIED')).toBe('Подтверждено');
  });

  it('maps verification status to existing badge colors without relying on color alone', () => {
    expect(verificationStatusClass('PENDING_VERIFICATION')).toContain('text-warning');
    expect(verificationStatusClass('VERIFIED')).toContain('text-success');
    expect(verificationStatusClass('REJECTED')).toContain('text-destructive');
    expect(verificationStatusClass('DRAFT')).toContain('text-muted-foreground');
  });
});

describe('partner legal type options', () => {
  it('offers only самозанятый / НПД, ИП and юридическое лицо', () => {
    const labels = subjectTypeOptions('partner').map((item) => item.label);
    expect(labels).toEqual(['Самозанятый / НПД', 'ИП', 'Юридическое лицо']);
    expect(labels.join(' ')).not.toContain('Физлицо');
    expect(labels.join(' ')).not.toContain('Физлицо / самозанятый');
    expect(subjectTypeOptions('partner').map((item) => item.value)).toEqual([
      'INDIVIDUAL',
      'SOLE_PROPRIETOR',
      'LEGAL_ENTITY',
    ]);
  });

  it('does not add ordinary individual to business options', () => {
    const labels = subjectTypeOptions('business').map((item) => item.label);
    expect(labels).toEqual(['ИП', 'Юридическое лицо']);
    expect(labels.join(' ')).not.toContain('Самозанятый');
    expect(labels.join(' ')).not.toContain('Физлицо');
  });

  it('locks самозанятый tax status to NPD and rejects Не указан', () => {
    expect(nextTaxStatusOnSubjectChange('partner', 'INDIVIDUAL', 'UNKNOWN')).toBe('NPD');
    expect(taxStatusOptions('partner', 'INDIVIDUAL', 'NPD').map((item) => item.value)).toEqual(['NPD']);
    expect(taxStatusOptions('partner', 'INDIVIDUAL', 'NPD').map((item) => item.value)).not.toContain('UNKNOWN');
    expect(partnerLegalFormError({ subject_type: 'INDIVIDUAL', tax_status: 'UNKNOWN' }, false)).toMatch(/НПД/);
    expect(partnerLegalFormError({ subject_type: 'INDIVIDUAL', tax_status: 'NPD' }, true)).toBeNull();
  });

  it('updates tax options when the partner type changes', () => {
    expect(nextTaxStatusOnSubjectChange('partner', 'SOLE_PROPRIETOR', 'NPD')).toBe('NPD');
    expect(taxStatusOptions('partner', 'SOLE_PROPRIETOR', 'NPD').map((item) => item.value)).toEqual([
      'NPD',
      'USN',
      'OSN',
      'PATENT',
      'OTHER',
    ]);
    expect(nextTaxStatusOnSubjectChange('partner', 'LEGAL_ENTITY', 'NPD')).toBe('UNKNOWN');
    expect(nextTaxStatusOnSubjectChange('partner', 'LEGAL_ENTITY', 'PATENT')).toBe('UNKNOWN');
    expect(nextTaxStatusOnSubjectChange('partner', 'LEGAL_ENTITY', 'USN')).toBe('USN');
    expect(taxStatusOptions('partner', 'LEGAL_ENTITY', 'USN').map((item) => item.value)).toEqual([
      'USN',
      'OSN',
      'OTHER',
    ]);
    expect(taxStatusOptions('partner', 'LEGAL_ENTITY', 'USN').map((item) => item.value)).not.toContain('NPD');
    expect(taxStatusOptions('partner', 'LEGAL_ENTITY', 'USN').map((item) => item.value)).not.toContain('PATENT');
  });

  it('keeps business tax options unchanged', () => {
    expect(taxStatusOptions('business', 'LEGAL_ENTITY', 'UNKNOWN').map((item) => item.value)).toEqual([
      'UNKNOWN',
      'NPD',
      'USN',
      'OSN',
      'PATENT',
      'OTHER',
    ]);
    expect(nextTaxStatusOnSubjectChange('business', 'LEGAL_ENTITY', 'NPD')).toBe('NPD');
  });

  it('does not treat a legacy individual without NPD as already valid', () => {
    expect(isUnsupportedPartnerIndividual('INDIVIDUAL', 'UNKNOWN')).toBe(true);
    expect(isUnsupportedPartnerIndividual('INDIVIDUAL', 'OTHER')).toBe(true);
    expect(isUnsupportedPartnerIndividual('INDIVIDUAL', 'NPD')).toBe(false);
  });
});
