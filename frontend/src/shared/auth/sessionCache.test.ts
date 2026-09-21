import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';
import {
  bindQueryClient,
  clearClientSession,
  SESSION_QUERY_KEY,
  shouldClearSessionOnUnauthorized,
  shouldRetryQuery,
} from './sessionCache';

describe('session cache', () => {
  it('clears a stale session and drops other cached queries on 401', () => {
    const client = new QueryClient();
    bindQueryClient(client);
    client.setQueryData(SESSION_QUERY_KEY, { user: { id: '1', roles: [{ role: 'business', status: 'active' }] } });
    client.setQueryData(['business', 'dashboard'], { kpis: {} });
    client.setQueryData(['notifications', 'unread-count'], { unread_count: 3 });

    clearClientSession();

    expect(client.getQueryData(SESSION_QUERY_KEY)).toBeNull();
    expect(client.getQueryData(['business', 'dashboard'])).toBeUndefined();
    expect(client.getQueryData(['notifications', 'unread-count'])).toBeUndefined();
  });

  it('does not retry unauthenticated queries', () => {
    expect(shouldRetryQuery(0, { status: 401 })).toBe(false);
    expect(shouldRetryQuery(0, { status: 403 })).toBe(false);
    expect(shouldRetryQuery(0, { status: 500 })).toBe(true);
    expect(shouldRetryQuery(1, { status: 500 })).toBe(false);
  });

  it('keeps the guest auth forms from wiping an in-flight register/login error', () => {
    expect(shouldClearSessionOnUnauthorized('/auth/login')).toBe(false);
    expect(shouldClearSessionOnUnauthorized('/auth/register')).toBe(false);
    expect(shouldClearSessionOnUnauthorized('/auth/session')).toBe(true);
    expect(shouldClearSessionOnUnauthorized('/business/dashboard?from=1')).toBe(true);
    expect(shouldClearSessionOnUnauthorized('/notifications/unread-count')).toBe(true);
  });
});
