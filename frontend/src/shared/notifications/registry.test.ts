import { describe, expect, it } from 'vitest';
import { notificationConfig, notificationDestination, notificationTitle } from './registry';
import type { AppNotification } from './types';

function item(overrides: Partial<AppNotification> = {}): AppNotification {
  return {
    id: 1,
    type: 'SDK_CONNECTED',
    severity: 'SUCCESS',
    title: 'SDK успешно подключён',
    message: 'shop.example.ru',
    is_read: false,
    created_at: '2026-09-01T10:00:00.000Z',
    read_at: null,
    destination: null,
    metadata: { site_id: 42, domain: 'shop.example.ru' },
    ...overrides,
  };
}

describe('notification registry', () => {
  it('resolves destination from registry without UI type switches', () => {
    expect(notificationDestination(item())).toBe('/business/settings?tab=sites&site=42');
    expect(notificationDestination(item({ type: 'PAYOUT_OVERDUE', metadata: {} }))).toBe(
      '/business/payouts',
    );
  });

  it('prefers destination from the notification model', () => {
    expect(notificationDestination(item({ destination: '/custom' }))).toBe('/custom');
  });

  it('falls back for unknown types without throwing', () => {
    const unknown = item({ type: 'FUTURE_TYPE', title: '', destination: null, metadata: {} });
    expect(notificationConfig(unknown.type).fallbackTitle).toBe('Уведомление');
    expect(notificationTitle(unknown)).toBe('Уведомление');
    expect(notificationDestination(unknown)).toBeNull();
  });
});
