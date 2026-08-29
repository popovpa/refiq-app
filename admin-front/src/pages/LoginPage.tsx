import { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Lock, Mail } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui';
import { errorMessage } from '@/lib/api';
import logoMark from '@/assets/brand/logo.png';
import logoLabel from '@/assets/brand/label.png';

export function LoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname || '/';

  if (isLoading) return null;
  if (isAuthenticated) return <Navigate to={from} replace />;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center gap-2 mb-6">
          <img src={logoMark} alt="" className="h-8" />
          <img src={logoLabel} alt="RefIQ" className="h-4" />
          <span className="text-xs uppercase tracking-wider text-muted-foreground">Admin</span>
        </div>
        <form
          className="ui-card p-6 space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setError('');
            setPending(true);
            try {
              await login(email, password);
            } catch (err) {
              setError(errorMessage(err, 'Не удалось войти'));
            } finally {
              setPending(false);
            }
          }}
        >
          <h1 className="text-lg font-semibold">Внутренняя консоль</h1>
          {error && <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md">{error}</div>}
          <label className="block">
            <span className="ui-label">Email</span>
            <div className="relative">
              <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input className="ui-input pl-9" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
          </label>
          <label className="block">
            <span className="ui-label">Пароль</span>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                className="ui-input pl-9"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </label>
          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? 'Вход…' : 'Войти'}
          </Button>
        </form>
      </div>
    </div>
  );
}
