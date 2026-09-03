import { describe, expect, it } from 'vitest';
import {
  QR_SLOT_ID,
  emptySelection,
  isKitSubmitValid,
  kitRequestPayload,
  recommendedSelection,
  selectAllSlots,
  selectNoneSlots,
  setQrTrackingLink,
  toggleSlot,
  type PromoLinkOption,
} from './kitSelection';

const CATALOG = [
  'telegram',
  'meta_ads',
  'google_ads',
  'yandex_direct',
  'vk_ads',
  'tiktok_ads',
  'images_1_1',
  'images_16_9',
  'images_9_16',
  QR_SLOT_ID,
];

const ONE_LINK: PromoLinkOption[] = [
  { id: 11, name: 'Лето', traffic_source: 'telegram', short_code: 'abc1234', url: 'https://go.refiq.ru/abc1234', status: 'ACTIVE' },
];

const TWO_LINKS: PromoLinkOption[] = [
  ...ONE_LINK,
  { id: 22, name: 'Осень', traffic_source: 'vk', short_code: 'def5678', url: 'https://go.refiq.ru/def5678', status: 'ACTIVE' },
];

describe('kit selection', () => {
  it('select all checks every enabled type and builds matching payload', () => {
    const state = selectAllSlots(CATALOG, TWO_LINKS);
    expect(state.selected).toEqual(CATALOG);
    expect(kitRequestPayload(state).slots).toEqual(CATALOG);
    expect(state.qrTrackingLinkId).toBeNull();
    expect(isKitSubmitValid(state)).toBe(false);
  });

  it('select all auto-picks the only tracking link for QR', () => {
    const state = selectAllSlots(CATALOG, ONE_LINK);
    expect(state.selected).toContain(QR_SLOT_ID);
    expect(state.qrTrackingLinkId).toBe('11');
    expect(isKitSubmitValid(state)).toBe(true);
    expect(kitRequestPayload(state).qr_tracking_link_id).toBe(11);
  });

  it('deselect all clears slots, QR link and disables submit', () => {
    const selected = selectAllSlots(CATALOG, ONE_LINK);
    const cleared = selectNoneSlots();
    expect(cleared.selected).toEqual([]);
    expect(cleared.qrTrackingLinkId).toBeNull();
    expect(isKitSubmitValid(cleared)).toBe(false);
    expect(kitRequestPayload(cleared).qr_tracking_link_id).toBeNull();
    expect(selected.selected.length).toBeGreaterThan(0);
  });

  it('maps each channel option to its generation type', () => {
    let state = emptySelection();
    for (const id of ['telegram', 'meta_ads', 'google_ads', 'yandex_direct', 'vk_ads', 'tiktok_ads']) {
      state = toggleSlot(state, id);
    }
    expect(kitRequestPayload(state).slots).toEqual([
      'telegram',
      'meta_ads',
      'google_ads',
      'yandex_direct',
      'vk_ads',
      'tiktok_ads',
    ]);
  });

  it('shows QR selector state for 0 / 1 / N links', () => {
    const none = toggleSlot(emptySelection(), QR_SLOT_ID, []);
    expect(none.qrTrackingLinkId).toBeNull();
    expect(isKitSubmitValid(none)).toBe(false);

    const one = toggleSlot(emptySelection(), QR_SLOT_ID, ONE_LINK);
    expect(one.qrTrackingLinkId).toBe('11');
    expect(isKitSubmitValid(one)).toBe(true);

    const many = toggleSlot(emptySelection(), QR_SLOT_ID, TWO_LINKS);
    expect(many.qrTrackingLinkId).toBeNull();
    expect(isKitSubmitValid(many)).toBe(false);
    const chosen = setQrTrackingLink(many, '22');
    expect(isKitSubmitValid(chosen)).toBe(true);
  });

  it('clears QR link when the QR slot is unchecked', () => {
    const on = toggleSlot(emptySelection(), QR_SLOT_ID, ONE_LINK);
    const off = toggleSlot(on, QR_SLOT_ID, ONE_LINK);
    expect(off.selected).not.toContain(QR_SLOT_ID);
    expect(off.qrTrackingLinkId).toBeNull();
    expect(isKitSubmitValid(off)).toBe(false);
  });

  it('does not restore recommended after an explicit empty selection', () => {
    const recommended = recommendedSelection(['telegram', 'images_1_1']);
    const cleared = selectNoneSlots();
    expect(cleared.selected).toEqual([]);
    expect(cleared).not.toEqual(recommended);
  });
});
