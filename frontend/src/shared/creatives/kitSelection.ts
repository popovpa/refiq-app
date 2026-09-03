export const QR_SLOT_ID = 'images_qr';

export type KitSelection = {
  selected: string[];
  qrTrackingLinkId: string | null;
};

export type PromoLinkOption = {
  id: string | number;
  name?: string | null;
  partner_name?: string | null;
  traffic_source?: string | null;
  short_code?: string;
  url: string;
  status: string;
};

export function emptySelection(): KitSelection {
  return { selected: [], qrTrackingLinkId: null };
}

export function recommendedSelection(recommended: string[]): KitSelection {
  return { selected: [...recommended], qrTrackingLinkId: null };
}

export function toggleSlot(state: KitSelection, id: string, links: PromoLinkOption[] = []): KitSelection {
  const selected = state.selected.includes(id)
    ? state.selected.filter((item) => item !== id)
    : [...state.selected, id];
  return syncQrLink({ ...state, selected }, links);
}

export function selectAllSlots(catalogIds: string[], links: PromoLinkOption[] = []): KitSelection {
  return syncQrLink({ selected: [...catalogIds], qrTrackingLinkId: null }, links);
}

export function selectNoneSlots(): KitSelection {
  return emptySelection();
}

export function setQrTrackingLink(state: KitSelection, qrTrackingLinkId: string | null): KitSelection {
  return { ...state, qrTrackingLinkId };
}

export function syncQrLink(state: KitSelection, links: PromoLinkOption[]): KitSelection {
  if (!state.selected.includes(QR_SLOT_ID)) {
    return { ...state, qrTrackingLinkId: null };
  }
  const active = activePromoLinks(links);
  if (state.qrTrackingLinkId && active.some((link) => String(link.id) === state.qrTrackingLinkId)) {
    return state;
  }
  if (active.length === 1) {
    return { ...state, qrTrackingLinkId: String(active[0].id) };
  }
  return { ...state, qrTrackingLinkId: null };
}

export function activePromoLinks(links: PromoLinkOption[]): PromoLinkOption[] {
  return links.filter((link) => String(link.status).toUpperCase() === 'ACTIVE');
}

export function allEnabledSelected(state: KitSelection, catalogIds: string[]): boolean {
  return catalogIds.length > 0 && catalogIds.every((id) => state.selected.includes(id));
}

export function hasSelection(state: KitSelection): boolean {
  return state.selected.length > 0;
}

export function qrSelected(state: KitSelection): boolean {
  return state.selected.includes(QR_SLOT_ID);
}

export function isKitSubmitValid(state: KitSelection): boolean {
  if (!hasSelection(state)) return false;
  if (qrSelected(state) && !state.qrTrackingLinkId) return false;
  return true;
}

export function kitRequestPayload(state: KitSelection): {
  slots: string[];
  qr_tracking_link_id: number | null;
} {
  return {
    slots: [...state.selected],
    qr_tracking_link_id: qrSelected(state) && state.qrTrackingLinkId ? Number(state.qrTrackingLinkId) : null,
  };
}

export function matchesLinkQuery(link: PromoLinkOption, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    link.name,
    link.partner_name,
    link.traffic_source,
    link.short_code,
    link.url,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(q);
}
