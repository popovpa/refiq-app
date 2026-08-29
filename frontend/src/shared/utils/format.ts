/** Safe number formatting for API payloads that may omit fields. */
export function formatNumber(value: number | string | null | undefined, fallback = '0'): string {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }
  const num = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(num)) {
    return fallback;
  }
  return num.toLocaleString('ru-RU');
}

export function formatMoney(
  value: number | string | null | undefined,
  currency = '₽',
): string {
  return `${formatNumber(value)} ${currency}`.trim();
}

export function formatCommission(
  rule?: { type?: string; value?: number | string | null; currency?: string | null } | null,
): string {
  if (!rule || rule.value === null || rule.value === undefined) {
    return '—';
  }
  if (rule.type === 'percent') {
    return `${formatNumber(rule.value)}%`;
  }
  return formatMoney(rule.value, rule.currency || '₽');
}
