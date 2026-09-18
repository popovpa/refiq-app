import { AlertTriangle } from 'lucide-react';

export function TestModeBanner({ visible }: { visible?: boolean }) {
  if (!visible) return null;
  return (
    <div className="rounded-lg border border-warning/30 bg-orange-50 px-4 py-3 text-sm text-warning">
      <p className="font-medium">Тестовый финансовый режим</p>
      <p className="mt-0.5 text-warning/80">Реальные платежи не выполняются.</p>
    </div>
  );
}

export function OverdueBanner({ visible, amount }: { visible?: boolean; amount?: number }) {
  if (!visible) return null;
  return (
    <div className="rounded-lg border border-destructive/30 bg-red-50 px-4 py-3 text-sm text-destructive flex gap-3">
      <AlertTriangle size={18} className="shrink-0 mt-0.5" />
      <div>
        <p className="font-medium">Просрочена выплата партнёру</p>
        <p className="mt-0.5 text-destructive/80">
          Партнёрский трафик приостановлен, пока задолженность не будет погашена
          {amount ? ` (${amount.toLocaleString('ru-RU')} ₽)` : ''}.
        </p>
      </div>
    </div>
  );
}
