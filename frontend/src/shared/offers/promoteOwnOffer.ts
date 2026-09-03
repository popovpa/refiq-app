export const OWN_OFFER_PROMOTE_TOAST =
  'Вы перешли в режим бизнеса. Собственный оффер продвигается от имени бизнеса без партнёрской комиссии.';

export const OWN_OFFER_PROMOTE_ERROR = 'Не удалось перейти в режим бизнеса. Попробуйте ещё раз.';

export const OWN_OFFER_PROMOTE_PENDING_LABEL = 'Переходим в режим бизнеса…';

export function ownOfferPromotePath(offerId: string | number): string {
  return `/business/offers/${offerId}?tab=promotion&createLink=1`;
}

export function ownOfferPromoteContext(offerId: string | number) {
  return { role: 'business' as const, offer_id: Number(offerId) };
}

export function canStartOwnOfferPromote(pending: boolean): boolean {
  return !pending;
}
