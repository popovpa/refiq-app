import { useState } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui';
import { validateReason } from '@/lib/reason';

export function ConfirmAction({
  title,
  description,
  confirmLabel,
  onConfirm,
  onClose,
  pending,
  destructive,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: (reason: string) => void;
  onClose: () => void;
  pending?: boolean;
  destructive?: boolean;
}) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    const message = validateReason(reason);
    if (message) {
      setError(message);
      return;
    }
    onConfirm(reason.trim());
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">{title}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <p className="text-sm text-muted-foreground">{description}</p>
        <div>
          <label className="ui-label" htmlFor="admin-reason">
            Причина
          </label>
          <textarea
            id="admin-reason"
            className="ui-input min-h-[88px] py-2"
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setError(null);
            }}
            required
          />
          {error && <p className="text-xs text-destructive mt-1">{error}</p>}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button variant={destructive ? 'destructive' : 'primary'} onClick={submit} disabled={pending}>
            {pending ? 'Выполняется…' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
