import { describe, expect, it } from 'vitest';
import { partnerAccessCta } from '@/shared/offers/partnerAccessCta';

describe('partnerAccessCta', () => {
  it('uses business-owned promotion CTA for the user own offer', () => {
    const cta = partnerAccessCta({ isOwn: true, accessPolicy: 'open', offerStatus: 'active' });
    expect(cta.kind).toBe('own-active');
    expect(cta.label).toBe('Продвигать свой оффер');
    expect(cta.label).not.toBe('Продвигать оффер');
  });

  it('asks to promote an approval offer before a request exists', () => {
    const cta = partnerAccessCta({ isOwn: false, accessPolicy: 'approval' });
    expect(cta.kind).toBe('promote-approval');
    expect(cta.label).toBe('Продвигать оффер');
  });

  it('locks a pending request as under review', () => {
    const cta = partnerAccessCta({ isOwn: false, accessPolicy: 'approval', partnerStatus: 'pending' });
    expect(cta.kind).toBe('pending');
    expect(cta.label).toBe('На рассмотрении');
    expect(cta.disabled).toBe(true);
  });

  it('opens the existing link flow after approval', () => {
    const cta = partnerAccessCta({ isOwn: false, accessPolicy: 'approval', partnerStatus: 'approved' });
    expect(cta.kind).toBe('create-link');
    expect(cta.label).toBe('Создать ссылку');
  });

  it('shows a rejection reason and a separate reapply action', () => {
    const cta = partnerAccessCta({
      isOwn: false,
      accessPolicy: 'approval',
      partnerStatus: 'rejected',
      rejectionReason: 'Не подходит аудитория',
    });
    expect(cta.kind).toBe('rejected');
    expect(cta.label).toBe('Доступ отклонён');
    expect(cta.reason).toBe('Не подходит аудитория');
    expect(cta.reapplyLabel).toBe('Продвигать оффер');
  });
});
