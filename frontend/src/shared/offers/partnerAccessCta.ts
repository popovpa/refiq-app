export type PartnerAccessCtaKind =
  | 'own-active'
  | 'own-paused'
  | 'create-link'
  | 'pending'
  | 'rejected'
  | 'promote-open'
  | 'promote-approval'
  | 'invite-only'
  | 'none';

export type PartnerAccessCta = {
  kind: PartnerAccessCtaKind;
  label: string;
  disabled?: boolean;
  note?: string | null;
  reason?: string | null;
  reapplyLabel?: string | null;
};

export function partnerAccessCta({
  isOwn,
  offerStatus,
  accessPolicy,
  partnerStatus,
  rejectionReason,
}: {
  isOwn: boolean;
  offerStatus?: string | null;
  accessPolicy: string;
  partnerStatus?: string | null;
  rejectionReason?: string | null;
}): PartnerAccessCta {
  if (isOwn) {
    if (offerStatus === 'paused') {
      return { kind: 'own-paused', label: 'Продвижение недоступно', disabled: true, note: 'Оффер приостановлен' };
    }
    return { kind: 'own-active', label: 'Продвигать свой оффер' };
  }
  if (partnerStatus === 'approved') {
    return { kind: 'create-link', label: 'Создать ссылку' };
  }
  if (partnerStatus === 'pending') {
    return { kind: 'pending', label: 'На рассмотрении', disabled: true };
  }
  if (partnerStatus === 'rejected') {
    return {
      kind: 'rejected',
      label: 'Доступ отклонён',
      disabled: true,
      note: 'Доступ отклонён',
      reason: rejectionReason?.trim() || null,
      reapplyLabel: 'Продвигать оффер',
    };
  }
  if (accessPolicy === 'open') {
    return { kind: 'promote-open', label: 'Продвигать оффер' };
  }
  if (accessPolicy === 'approval') {
    return { kind: 'promote-approval', label: 'Продвигать оффер' };
  }
  if (accessPolicy === 'invite_only') {
    return { kind: 'invite-only', label: 'Только по приглашению', disabled: true };
  }
  return { kind: 'none', label: '' };
}
