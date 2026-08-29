import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Lock } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { authApi } from '@/shared/api/auth';
import { AuthField } from './AuthField';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token')?.trim() || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [state, setState] = useState<'form' | 'success' | 'invalid'>(token ? 'form' : 'invalid');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!password || !confirmPassword) {
      setError('Заполните оба поля');
      return;
    }
    if (password.length < 8) {
      setError('Пароль должен содержать не менее 8 символов');
      return;
    }
    if (password.length > 128) {
      setError('Пароль слишком длинный');
      return;
    }
    if (password !== confirmPassword) {
      setError('Пароли не совпадают');
      return;
    }

    setPending(true);
    try {
      await authApi.resetPassword({ token, password });
      setState('success');
    } catch (err: unknown) {
      const code = (err as { error?: { code?: string } } | null)?.error?.code;
      const message = (err as { error?: { message?: string } } | null)?.error?.message;
      if (code === 'RESET_TOKEN_INVALID') {
        setState('invalid');
        return;
      }
      setError(message || 'Не удалось сохранить пароль. Попробуйте позже.');
    } finally {
      setPending(false);
    }
  };

  if (state === 'success') {
    return (
      <div className="space-y-5">
        <h2 className="text-2xl font-semibold text-center tracking-tight">Пароль успешно изменён</h2>
        <p className="text-sm text-center text-muted-foreground">
          Теперь войдите с новым паролем
        </p>
        <Link to="/login" className="block">
          <Button type="button" size="lg" className="w-full">
            Войти
          </Button>
        </Link>
      </div>
    );
  }

  if (state === 'invalid') {
    return (
      <div className="space-y-5">
        <h2 className="text-2xl font-semibold text-center tracking-tight">Ссылка недействительна</h2>
        <p className="text-sm text-center text-muted-foreground">
          Ссылка для восстановления пароля недействительна или уже истекла.
        </p>
        <Link to="/forgot-password" className="block">
          <Button type="button" size="lg" className="w-full">
            Запросить новую ссылку
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="text-center space-y-1.5">
        <h2 className="text-2xl font-semibold tracking-tight">Новый пароль</h2>
        <p className="text-sm text-muted-foreground">Задайте пароль для входа в RefIQ</p>
      </div>
      {error && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{error}</div>
      )}
      <AuthField
        id="reset-password"
        label="Новый пароль"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete="new-password"
        leftIcon={<Lock size={16} />}
        required
        minLength={8}
      />
      <AuthField
        id="reset-confirm-password"
        label="Подтвердите новый пароль"
        type="password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        autoComplete="new-password"
        leftIcon={<Lock size={16} />}
        required
        minLength={8}
      />
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? 'Сохранение...' : 'Сохранить новый пароль'}
      </Button>
    </form>
  );
}
