import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authApi, type SessionData, type LoginData, type RegisterData } from '@/shared/api/auth';
import { SESSION_QUERY_KEY } from '@/shared/auth/sessionCache';
import { postAuthPath } from '@/shared/layout/roleContext';

export async function fetchSession(): Promise<SessionData | null> {
  try {
    return await authApi.getSession();
  } catch (err: unknown) {
    const status = (err as { status?: number } | null)?.status;
    // 401/403 = guest. Any other failure also treated as logged-out
    // so auth pages never stick on the spinner.
    if (status === 401 || status === 403) {
      return null;
    }
    console.error('Session check failed', err);
    return null;
  }
}

function resetClientAuth(queryClient: QueryClient) {
  queryClient.setQueryData(SESSION_QUERY_KEY, null);
  queryClient.clear();
}

export function useAuth() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: session, isPending } = useQuery<SessionData | null>({
    queryKey: SESSION_QUERY_KEY,
    queryFn: fetchSession,
    retry: false,
    staleTime: 30000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const loginMutation = useMutation({
    mutationFn: (data: LoginData) => authApi.login(data),
    onSuccess: (data) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, data);
      navigate(postAuthPath(data));
    },
  });

  const registerMutation = useMutation({
    mutationFn: (data: RegisterData) => authApi.register(data),
  });

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      resetClientAuth(queryClient);
      navigate('/login');
    },
  });

  return {
    user: session?.user ?? null,
    session: session ?? null,
    isLoading: isPending,
    isAuthenticated: !!session?.user,
    login: loginMutation,
    register: registerMutation,
    logout: logoutMutation,
  };
}

/** Re-check the cookie session before trusting cached auth on public/onboarding routes. */
export function useFreshSession() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    queryClient
      .fetchQuery({
        queryKey: SESSION_QUERY_KEY,
        queryFn: fetchSession,
        staleTime: 0,
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [queryClient]);

  return {
    ...auth,
    isLoading: auth.isLoading || !ready,
  };
}
