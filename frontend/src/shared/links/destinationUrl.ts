import { TRACKING_HOST } from '@/shared/offers/trackingLink';

const TRACKER_HOSTS = new Set([TRACKING_HOST, `www.${TRACKING_HOST}`]);

export function validateDestinationUrl(raw: string): { ok: true; value: string } | { ok: false; message: string } {
  const value = raw.trim();
  if (!value) {
    return { ok: false, message: 'Введите корректный URL' };
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return { ok: false, message: 'Введите корректный URL' };
  }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    return { ok: false, message: 'Введите корректный URL' };
  }
  const hostname = parsed.hostname.toLowerCase().replace(/\.$/, '');
  if (!hostname || !hostname.includes('.')) {
    return { ok: false, message: 'Введите корректный URL' };
  }
  if (TRACKER_HOSTS.has(hostname) || hostname.endsWith(`.${TRACKING_HOST}`)) {
    return { ok: false, message: 'Этот домен нельзя использовать для данной ссылки' };
  }
  return { ok: true, value };
}

export function siteHostname(url?: string | null) {
  if (!url?.trim()) return '';
  try {
    const withProtocol = /^https?:\/\//i.test(url.trim()) ? url.trim() : `https://${url.trim()}`;
    return new URL(withProtocol).hostname.replace(/\.$/, '').toLowerCase();
  } catch {
    return '';
  }
}
