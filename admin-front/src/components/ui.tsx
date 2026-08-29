import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { CheckCircle2, X, AlertCircle, Info } from 'lucide-react';
import { createContext, useCallback, useContext, useState } from 'react';
import { formatDate as formatDateTime, formatNumber } from '@/lib/utils';
import { statusLabel } from '@/lib/labels';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export { formatDateTime, formatNumber };

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'destructive' | 'outline';
  size?: 'sm' | 'md' | 'lg';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-all',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        'disabled:pointer-events-none disabled:opacity-50',
        {
          'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm': variant === 'primary',
          'bg-secondary text-secondary-foreground hover:bg-secondary/80': variant === 'secondary',
          'hover:bg-muted text-foreground': variant === 'ghost',
          'bg-destructive text-destructive-foreground hover:bg-destructive/90': variant === 'destructive',
          'border border-primary/30 bg-card text-primary hover:bg-accent': variant === 'outline',
        },
        {
          'h-8 px-3 text-xs': size === 'sm',
          'h-9 px-3.5 text-sm': size === 'md',
          'h-11 px-5 text-sm': size === 'lg',
        },
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = 'Button';

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} />;
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="ui-card flex flex-col items-center justify-center py-12 px-6 text-center">
      <h3 className="text-sm font-semibold text-foreground mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-md mb-4">{description}</p>
      {action && (
        <Button size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}

export function StatusBadge({ status }: { status?: string | null }) {
  const value = (status || 'unknown').toLowerCase();
  const tone =
    ['active', 'approved', 'accepted', 'paid', 'healthy', 'ok', 'success', 'attributed', 'calculated', 'connected'].includes(value)
      ? 'bg-success/10 text-success'
      : ['paused', 'pending', 'waiting_approval', 'degraded', 'no_activity', 'awaiting_first_request', 'processing', 'duplicate'].includes(value)
        ? 'bg-warning/10 text-warning'
        : ['suspended', 'blocked', 'rejected', 'error', 'failed', 'cancelled', 'inactive', 'disabled', 'not_connected'].includes(value)
          ? 'bg-destructive/10 text-destructive'
          : 'bg-muted text-muted-foreground';
  return <span className={cn('ui-badge', tone)}>{statusLabel(status)}</span>;
}

export function CopyId({ value }: { value?: string | number | null }) {
  if (value === null || value === undefined || value === '') return <span>—</span>;
  return (
    <button
      type="button"
      className="font-mono text-xs text-muted-foreground hover:text-foreground"
      onClick={() => navigator.clipboard.writeText(String(value))}
      title="Скопировать ID"
    >
      {String(value)}
    </button>
  );
}

export function Kv({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[160px_1fr] gap-3 py-1.5 text-sm border-b border-border/60 last:border-0">
      <div className="text-muted-foreground">{label}</div>
      <div className="min-w-0 break-words">{children ?? '—'}</div>
    </div>
  );
}

export function PageTitle({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 mb-4">
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

const ToastContext = createContext<{
  addToast: (message: string, type?: Toast['type']) => void;
} | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const addToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);
  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              'pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg border shadow-soft bg-card text-sm',
              toast.type === 'success' && 'border-success/20',
              toast.type === 'error' && 'border-destructive/20',
              toast.type === 'info' && 'border-border',
            )}
          >
            {toast.type === 'success' && <CheckCircle2 size={18} className="text-success shrink-0 mt-0.5" />}
            {toast.type === 'error' && <AlertCircle size={18} className="text-destructive shrink-0 mt-0.5" />}
            {toast.type === 'info' && <Info size={18} className="text-info shrink-0 mt-0.5" />}
            <p className="flex-1 font-medium leading-snug">{toast.message}</p>
            <button type="button" onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}>
              <X size={14} className="text-muted-foreground" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
