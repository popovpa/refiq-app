import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/hooks/useAuth';
import { useToast } from '@/shared/components/Toast';
import { rolesApi } from '@/shared/api/roles';
import { OnboardingWizard } from '@/shared/onboarding/OnboardingWizard';
import { postAuthPath } from '@/shared/layout/roleContext';
import { financeApiErrorText } from '@/shared/finance/messages';
import type { SessionData } from '@/shared/api/auth';

export function OnboardingPage() {
  const { user, logout } = useAuth();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState('');

  const applySession = (data: SessionData) => {
    queryClient.setQueryData(['session'], data);
    queryClient.invalidateQueries({ queryKey: ['profile'] });
    navigate(postAuthPath(data), { replace: true });
  };

  const partnerMutation = useMutation({
    mutationFn: rolesApi.activatePartner,
    onSuccess: (data) => {
      addToast('Роль Партнёра подключена', 'success');
      applySession(data);
    },
    onError: (err) => setError(financeApiErrorText(err, 'Не удалось подключить роль. Попробуйте ещё раз.')),
  });

  const businessMutation = useMutation({
    mutationFn: rolesApi.activateBusiness,
    onSuccess: (data) => {
      addToast('Роль Бизнеса подключена', 'success');
      applySession(data);
    },
    onError: (err) => setError(financeApiErrorText(err, 'Не удалось подключить роль. Попробуйте ещё раз.')),
  });

  const pending = partnerMutation.isPending || businessMutation.isPending;
  const fullName = [user?.last_name, user?.first_name].filter(Boolean).join(' ');

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1.5">
        <p className="text-sm text-muted-foreground">Добро пожаловать</p>
        <h1 className="text-2xl font-semibold tracking-tight">Как вы хотите использовать RefIQ?</h1>
      </div>
      <OnboardingWizard
        userEmail={user?.email}
        userName={fullName}
        userPhone={user?.phone || ''}
        pending={pending}
        error={error}
        onError={setError}
        onSaveBusiness={(payload) => businessMutation.mutate(payload)}
        onSavePartner={(payload) => partnerMutation.mutate(payload)}
      />
      <p className="text-center text-sm text-muted-foreground">
        <button type="button" className="text-primary font-medium hover:underline" onClick={() => logout.mutate()}>
          Выйти
        </button>
      </p>
    </div>
  );
}
