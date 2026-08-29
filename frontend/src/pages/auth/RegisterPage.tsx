import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/shared/hooks/useAuth';
import { useToast } from '@/shared/components/Toast';
import { Button } from '@/shared/components/Button';
import { AuthField } from './AuthField';

export function RegisterPage() {
  const { register } = useAuth();
  const { addToast } = useToast();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
  });
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [error, setError] = useState('');
  const [submittedEmail, setSubmittedEmail] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Пароли не совпадают');
      return;
    }
    if (!acceptedTerms) {
      setError('Чтобы продолжить, примите условия использования');
      return;
    }

    register.mutate(
      {
        email: formData.email,
        password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
      },
      {
        onSuccess: () => {
          setSubmittedEmail(formData.email);
        },
        onError: (err: unknown) => {
          const message = (err as { error?: { message?: string } } | null)?.error?.message;
          setError(message || 'Ошибка регистрации');
        },
      },
    );
  };

  if (submittedEmail) {
    return (
      <div className="space-y-5">
        <div className="text-center space-y-1.5">
          <h2 className="text-2xl font-semibold tracking-tight">Проверьте почту</h2>
          <p className="text-sm text-muted-foreground">
            Мы отправили письмо для подтверждения аккаунта на {submittedEmail}.
            Перейдите по ссылке в письме, чтобы активировать аккаунт.
          </p>
        </div>
        <p className="text-sm text-center text-muted-foreground">
          <Link to="/login" className="text-primary font-medium hover:underline">
            Войти
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="text-center space-y-1.5">
        <h2 className="text-2xl font-semibold tracking-tight">Регистрация</h2>
        <p className="text-sm text-muted-foreground">
          Создайте аккаунт и получите доступ к платформе
        </p>
      </div>
      {error && (
        <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{error}</div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <AuthField
          id="register-first-name"
          label="Имя"
          value={formData.first_name}
          onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
          autoComplete="given-name"
          required
        />
        <AuthField
          id="register-last-name"
          label="Фамилия"
          value={formData.last_name}
          onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
          autoComplete="family-name"
          required
        />
      </div>
      <AuthField
        id="register-email"
        label="Email"
        type="email"
        value={formData.email}
        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
        autoComplete="email"
        required
      />
      <AuthField
        id="register-password"
        label="Пароль"
        type="password"
        value={formData.password}
        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
        autoComplete="new-password"
        required
        minLength={8}
      />
      <AuthField
        id="register-confirm-password"
        label="Подтверждение пароля"
        type="password"
        value={formData.confirmPassword}
        onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
        autoComplete="new-password"
        required
        minLength={8}
      />
      <label className="flex items-start gap-2.5 text-sm text-foreground cursor-pointer select-none">
        <input
          type="checkbox"
          checked={acceptedTerms}
          onChange={(e) => setAcceptedTerms(e.target.checked)}
          className="mt-0.5 h-4 w-4 shrink-0 rounded border-input accent-primary"
        />
        <span>
          Я соглашаюсь с{' '}
          <button
            type="button"
            className="text-primary font-medium hover:underline"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              addToast('Условия использования скоро будут доступны', 'info');
            }}
          >
            условиями использования
          </button>{' '}
          и{' '}
          <button
            type="button"
            className="text-primary font-medium hover:underline"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              addToast('Политика конфиденциальности скоро будет доступна', 'info');
            }}
          >
            политикой конфиденциальности
          </button>
        </span>
      </label>
      <Button type="submit" size="lg" className="w-full" disabled={register.isPending}>
        {register.isPending ? 'Регистрация...' : 'Зарегистрироваться'}
      </Button>
      <p className="text-sm text-center text-muted-foreground">
        Уже есть аккаунт?{' '}
        <Link to="/login" className="text-primary font-medium hover:underline">
          Войти
        </Link>
      </p>
    </form>
  );
}
