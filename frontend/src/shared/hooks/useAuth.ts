import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authApi, type SessionData, type LoginData, type RegisterData } from '@/shared/api/auth';
import { postAuthPath } from '@/shared/layout/roleContext';

async function fetchSession(): Promise<SessionData | null> {
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

export function useAuth() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: session, isPending } = useQuery<SessionData | null>({
    queryKey: ['session'],
    queryFn: fetchSession,
    retry: false,
    staleTime: 30000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const loginMutation = useMutation({
    mutationFn: (data: LoginData) => authApi.login(data),
    onSuccess: (data) => {
      queryClient.setQueryData(['session'], data);
      navigate(postAuthPath(data));
    },
  });

  const registerMutation = useMutation({
    mutationFn: (data: RegisterData) => authApi.register(data),
  });

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.setQueryData(['session'], null);
      queryClient.clear();
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
