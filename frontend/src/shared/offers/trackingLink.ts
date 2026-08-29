export const TRACKING_HOST = 'go.refiq.ru';

export function publicTrackingUrl(shortCode: string): string {
  return `https://${TRACKING_HOST}/${shortCode}`;
}

export function displayTrackingUrl(shortCode: string): string {
  return `${TRACKING_HOST}/${shortCode}`;
}

export function partnerQrCodePath(linkId: string | number): string {
  return `/partner/links/${linkId}/qr-code`;
}

export function partnerQrCodeUrl(linkId: string | number): string {
  return `/api/v1${partnerQrCodePath(linkId)}`;
}

export function partnerQrCodeDownloadPath(linkId: string | number): string {
  return `${partnerQrCodePath(linkId)}/download`;
}

export function businessQrCodePath(offerId: string | number, linkId: string | number): string {
  return `/business/offers/${offerId}/links/${linkId}/qr-code`;
}

export function businessQrCodeUrl(offerId: string | number, linkId: string | number): string {
  return `/api/v1${businessQrCodePath(offerId, linkId)}`;
}

export function businessQrCodeDownloadPath(offerId: string | number, linkId: string | number): string {
  return `${businessQrCodePath(offerId, linkId)}/download`;
}
