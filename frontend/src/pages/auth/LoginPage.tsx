import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Lock, Mail } from 'lucide-react';
import { useAuth } from '@/shared/hooks/useAuth';
import { Button } from '@/shared/components/Button';
import { AuthField } from './AuthField';

const REMEMBER_EMAIL_KEY = 'refiq_remembered_email';

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const saved = localStorage.getItem(REMEMBER_EMAIL_KEY);
    if (saved) {
      setEmail(saved);
      setRememberMe(true);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    login.mutate(
      { email, password },
      {
        onSuccess: () => {
          if (rememberMe) {
            localStorage.setItem(REMEMBER_EMAIL_KEY, email);
          } else {
            localStorage.removeItem(REMEMBER_EMAIL_KEY);
          }
        },
        onError: (err: unknown) => {
          const message = (err as { error?: { message?: string } } | null)?.error?.message;
          setError(message || 'Ошибка входа');
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <h2 className="text-2xl font-semibold text-center tracking-tight">Вход</h2>
      {error && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{error}</div>
      )}
      <AuthField
        id="login-email"
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Введите email"
        autoComplete="email"
        leftIcon={<Mail size={16} />}
        required
      />
      <AuthField
        id="login-password"
        label="Пароль"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Введите пароль"
        autoComplete="current-password"
        leftIcon={<Lock size={16} />}
        required
      />
      <div className="flex items-center justify-between gap-3 text-sm">
        <label className="inline-flex items-center gap-2 text-foreground cursor-pointer select-none">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            className="h-4 w-4 rounded border-input accent-primary"
          />
          Запомнить меня
        </label>
        <Link to="/forgot-password" className="text-primary font-medium hover:underline">
          Забыли пароль?
        </Link>
      </div>
      <Button type="submit" size="lg" className="w-full" disabled={login.isPending}>
        {login.isPending ? 'Вход...' : 'Войти'}
      </Button>
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-card px-3 text-muted-foreground">или</span>
        </div>
      </div>
      <p className="text-sm text-center text-muted-foreground">
        Нет аккаунта?{' '}
        <Link to="/register" className="text-primary font-medium hover:underline">
          Зарегистрироваться
        </Link>
      </p>
    </form>
  );
}
