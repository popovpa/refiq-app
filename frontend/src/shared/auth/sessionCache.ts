import type { QueryClient } from '@tanstack/react-query';

export const SESSION_QUERY_KEY = ['session'] as const;

let queryClient: QueryClient | null = null;

export function bindQueryClient(client: QueryClient) {
  queryClient = client;
}

export function shouldRetryQuery(failureCount: number, error: unknown) {
  const status = (error as { status?: number } | null)?.status;
  if (status === 401 || status === 403) return false;
  return failureCount < 1;
}

const KEEP_SESSION_ON_401 = new Set([
  '/auth/login',
  '/auth/register',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/confirm-email',
]);

export function shouldClearSessionOnUnauthorized(endpoint: string) {
  const path = endpoint.split('?')[0];
  return !KEEP_SESSION_ON_401.has(path);
}

export function clearClientSession() {
  if (!queryClient) return;
  queryClient.setQueryData(SESSION_QUERY_KEY, null);
  queryClient.removeQueries({
    predicate: (query) => query.queryKey[0] !== SESSION_QUERY_KEY[0],
  });
}
