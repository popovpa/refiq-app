export function validateReason(reason: string) {
  const value = reason.trim();
  if (!value) return 'Укажите причину';
  if (value.length > 500) return 'Причина не должна превышать 500 символов';
  return null;
}
