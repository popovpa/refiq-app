export function canManuallyReviewLegalEntity(status?: string | null) {
  return status === 'PENDING_VERIFICATION';
}

export const REJECT_REASON_OPTIONS = [
  { value: 'INN_NOT_FOUND', label: 'ИНН не найден' },
  { value: 'ENTITY_INACTIVE', label: 'Субъект не действует' },
  { value: 'DATA_MISMATCH', label: 'Данные не совпадают' },
  { value: 'UNSUPPORTED_ENTITY_TYPE', label: 'Недопустимый тип субъекта' },
  { value: 'INVALID_LEGAL_DATA', label: 'Некорректные юридические данные' },
  { value: 'OTHER', label: 'Другое' },
] as const;

export const OWNER_TYPE_LABELS: Record<string, string> = {
  business: 'Бизнес',
  partner: 'Партнёр',
  shared: 'Бизнес и партнёр',
};

export function ownerTypeLabel(type?: string | null) {
  if (!type) return '—';
  return OWNER_TYPE_LABELS[type] || type;
}
