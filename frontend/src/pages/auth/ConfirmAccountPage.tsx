import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/shared/components/Button';
import { authApi } from '@/shared/api/auth';
import { postAuthPath } from '@/shared/layout/roleContext';

export function ConfirmAccountPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token')?.trim() || '';
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [state, setState] = useState<'loading' | 'activated' | 'invalid'>(token ? 'loading' : 'invalid');
  const [entering, setEntering] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) {
      setState('invalid');
      return;
    }
    let cancelled = false;
    authApi
      .confirmEmail({ token })
      .then(() => {
        if (!cancelled) setState('activated');
      })
      .catch(() => {
        if (!cancelled) setState('invalid');
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const enterService = async () => {
    setError('');
    setEntering(true);
    try {
      const session = await authApi.confirmEmailLogin({ token });
      queryClient.setQueryData(['session'], session);
      navigate(postAuthPath(session));
    } catch (err: unknown) {
      const message = (err as { error?: { message?: string } } | null)?.error?.message;
      setError(message || 'Не удалось войти. Попробуйте войти с паролем.');
    } finally {
      setEntering(false);
    }
  };

  if (state === 'loading') {
    return (
      <div className="space-y-5 text-center">
        <h2 className="text-2xl font-semibold tracking-tight">Подтверждение аккаунта</h2>
        <p className="text-sm text-muted-foreground">Проверяем ссылку...</p>
      </div>
    );
  }

  if (state === 'invalid') {
    return (
      <div className="space-y-5">
        <h2 className="text-2xl font-semibold text-center tracking-tight">Ссылка недействительна</h2>
        <p className="text-sm text-center text-muted-foreground">
          Ссылка для подтверждения аккаунта недействительна или уже истекла.
        </p>
        <Link to="/login" className="block">
          <Button type="button" size="lg" className="w-full">
            Войти
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="text-center space-y-1.5">
        <h2 className="text-2xl font-semibold tracking-tight">Аккаунт подтверждён</h2>
        <p className="text-sm text-muted-foreground">
          Email подтверждён, аккаунт активирован. Можно переходить в сервис.
        </p>
      </div>
      {error && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{error}</div>
      )}
      <Button type="button" size="lg" className="w-full" onClick={enterService} disabled={entering}>
        {entering ? 'Вход...' : 'Перейти в сервис'}
      </Button>
    </div>
  );
}
