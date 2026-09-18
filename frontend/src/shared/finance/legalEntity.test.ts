import { describe, expect, it } from 'vitest';
import { legalEntityWritePayload, verificationStatusClass, verificationStatusLabel } from './legalEntity';

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
