import { useState } from 'react';
import { Briefcase, Users } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/hooks/useAuth';
import { useToast } from '@/shared/components/Toast';
import { Button } from '@/shared/components/Button';
import { rolesApi, type ActivateBusinessPayload } from '@/shared/api/roles';
import { BecomeBusinessForm } from '@/shared/onboarding/BecomeBusinessForm';
import { postAuthPath } from '@/shared/layout/roleContext';
import type { SessionData } from '@/shared/api/auth';
import { cn } from '@/shared/utils/cn';

export function OnboardingPage() {
  const { user, logout } = useAuth();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'choose' | 'business'>('choose');
  const [error, setError] = useState('');

  const applySession = (data: SessionData) => {
    queryClient.setQueryData(['session'], data);
    queryClient.invalidateQueries({ queryKey: ['profile'] });
    navigate(postAuthPath(data), { replace: true });
  };

  const partnerMutation = useMutation({
    mutationFn: () => rolesApi.activatePartner(),
    onSuccess: (data) => {
      addToast('Роль Партнёра подключена', 'success');
      applySession(data);
    },
    onError: () => {
      setError('Не удалось подключить роль. Попробуйте ещё раз.');
    },
  });

  const businessMutation = useMutation({
    mutationFn: (payload: ActivateBusinessPayload) => rolesApi.activateBusiness(payload),
    onSuccess: (data) => {
      addToast('Роль Бизнеса подключена', 'success');
      applySession(data);
    },
    onError: () => {
      setError('Не удалось подключить роль. Попробуйте ещё раз.');
    },
  });

  const pending = partnerMutation.isPending || businessMutation.isPending;

  return (
    <div className="space-y-6">
      <div className="text-center space-y-1.5">
        <p className="text-sm text-muted-foreground">Добро пожаловать</p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {mode === 'business' ? 'Данные компании' : 'Как вы хотите использовать RefIQ?'}
        </h1>
        {mode === 'business' && (
          <p className="text-sm text-muted-foreground">
            Коротко о бизнесе — оффер создадите уже в рабочем пространстве.
          </p>
        )}
      </div>

      {error && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{error}</div>
      )}

      {mode === 'choose' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <ChoiceCard
            icon={Users}
            title="Партнёр"
            description="Продвигайте офферы компаний и получайте комиссию с конверсий."
            action="Стать партнёром"
            pending={partnerMutation.isPending}
            disabled={pending}
            onClick={() => {
              setError('');
              partnerMutation.mutate();
            }}
          />
          <ChoiceCard
            icon={Briefcase}
            title="Бизнес"
            description="Создавайте офферы, подключайте партнёров и развивайте продажи."
            action="Стать бизнесом"
            disabled={pending}
            onClick={() => {
              setError('');
              setMode('business');
            }}
          />
        </div>
      ) : (
        <div className="space-y-4">
          <BecomeBusinessForm
            defaults={{
              work_email: user?.email || '',
              phone: user?.phone || '',
            }}
            pending={businessMutation.isPending}
            onSubmit={(payload) => {
              setError('');
              businessMutation.mutate(payload);
            }}
          />
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            disabled={pending}
            onClick={() => setMode('choose')}
          >
            Назад
          </Button>
        </div>
      )}

      <p className="text-center text-sm text-muted-foreground">
        <button type="button" className="text-primary font-medium hover:underline" onClick={() => logout.mutate()}>
          Выйти
        </button>
      </p>
    </div>
  );
}

function ChoiceCard({
  icon: Icon,
  title,
  description,
  action,
  pending,
  disabled,
  onClick,
}: {
  icon: typeof Users;
  title: string;
  description: string;
  action: string;
  pending?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'ui-card p-5 text-left space-y-4 transition-colors',
        'hover:border-primary/30 hover:bg-accent/40',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        'disabled:pointer-events-none disabled:opacity-60',
      )}
    >
      <div className="w-9 h-9 rounded-md bg-accent text-primary flex items-center justify-center">
        <Icon size={18} />
      </div>
      <div className="space-y-1.5">
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </div>
      <span className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">
        {pending ? 'Подключение...' : action}
      </span>
    </button>
  );
}
