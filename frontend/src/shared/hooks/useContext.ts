import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import type { SessionData } from '@/shared/api/auth';

export function useRoleContext() {
  const queryClient = useQueryClient();

  const switchRole = useMutation({
    mutationFn: (role: string) => api.post<SessionData>('/me/context', { role }),
    onSuccess: (data) => {
      queryClient.setQueryData(['session'], data);
    },
  });

  return { switchRole };
}
