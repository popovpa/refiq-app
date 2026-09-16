const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/i;

export function partnerDisplayName(
  name?: string | null,
  partnerId?: number | string | null,
): string {
  const trimmed = (name || '').trim();
  if (trimmed && !EMAIL_RE.test(trimmed) && !trimmed.includes('@')) {
    return trimmed;
  }
  if (partnerId != null && String(partnerId).length > 0) {
    return `Партнёр #${partnerId}`;
  }
  if (trimmed) {
    return 'Партнёр';
  }
  return '';
}
