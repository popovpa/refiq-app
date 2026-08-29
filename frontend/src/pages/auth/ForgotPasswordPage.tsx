import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { authApi } from '@/shared/api/auth';
import { AuthField } from './AuthField';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setPending(true);
    try {
      await authApi.forgotPassword({ email });
      setSubmitted(true);
    } catch (err: unknown) {
      const message = (err as { error?: { message?: string } } | null)?.error?.message;
      setError(message || 'Не удалось отправить запрос. Попробуйте позже.');
    } finally {
      setPending(false);
    }
  };

  if (submitted) {
    return (
      <div className="space-y-5">
        <h2 className="text-2xl font-semibold text-center tracking-tight">Восстановление пароля</h2>
        <p className="text-sm text-center text-muted-foreground">
          Если аккаунт с таким email существует, мы отправили ссылку для восстановления пароля.
        </p>
        <p className="text-sm text-center text-muted-foreground">
          <Link to="/login" className="text-primary font-medium hover:underline">
            Вернуться ко входу
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="text-center space-y-1.5">
        <h2 className="text-2xl font-semibold tracking-tight">Восстановление пароля</h2>
        <p className="text-sm text-muted-foreground">
          Укажите email — мы отправим ссылку для смены пароля
        </p>
      </div>
      {error && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{error}</div>
      )}
      <AuthField
        id="forgot-email"
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="user@example.com"
        autoComplete="email"
        leftIcon={<Mail size={16} />}
        required
      />
      <Button type="submit" size="lg" className="w-full" disabled={pending}>
        {pending ? 'Отправка...' : 'Восстановить пароль'}
      </Button>
      <p className="text-sm text-center text-muted-foreground">
        Вспомнили пароль?{' '}
        <Link to="/login" className="text-primary font-medium hover:underline">
          Войти
        </Link>
      </p>
    </form>
  );
}
