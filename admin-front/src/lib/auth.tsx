import { createContext, useContext, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, isApiError } from './api';
import { hasPermission } from './permissions';

export interface AdminSession {
  id: number;
  email: string;
  role: string;
  permissions: string[];
  status: string;
  last_login_at?: string | null;
}

interface AuthContextValue {
  session: AdminSession | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  has: (permission: string) => boolean;
  login: (email: string, password: string) => Promise<AdminSession>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchSession(): Promise<AdminSession | null> {
  try {
    return await api.get<AdminSession>('/auth/session');
  } catch (err) {
    if (isApiError(err) && (err.status === 401 || err.status === 403)) return null;
    throw err;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['admin-session'],
    queryFn: fetchSession,
    retry: false,
    staleTime: 60_000,
  });

  const loginMutation = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.post<AdminSession>('/auth/login', { email, password }),
    onSuccess: (session) => {
      queryClient.setQueryData(['admin-session'], session);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => api.post('/auth/logout'),
    onSuccess: () => {
      queryClient.setQueryData(['admin-session'], null);
      queryClient.clear();
    },
  });

  const session = query.data ?? null;
  const value: AuthContextValue = {
    session,
    isLoading: query.isLoading,
    isAuthenticated: Boolean(session),
    has: (permission) => hasPermission(session?.permissions, permission),
    login: (email, password) => loginMutation.mutateAsync({ email, password }),
    logout: () => logoutMutation.mutateAsync().then(() => undefined),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
