import type { ReactNode } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';

export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  onConfirm,
  onClose,
  pending,
  cancelLabel,
  pendingLabel,
  confirmDisabled,
  confirmVariant = 'primary',
  className,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  pending?: boolean;
  cancelLabel?: string;
  pendingLabel?: string;
  confirmDisabled?: boolean;
  confirmVariant?: 'primary' | 'destructive';
  className?: string;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className={cn('relative ui-card w-full max-w-md p-5 space-y-4 shadow-soft', className)}>
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">{title}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <div className="text-sm text-muted-foreground space-y-2">{children}</div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {cancelLabel ?? 'Отмена'}
          </Button>
          <Button variant={confirmVariant} onClick={onConfirm} disabled={pending || confirmDisabled}>
            {pending ? pendingLabel ?? 'Сохранение...' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
