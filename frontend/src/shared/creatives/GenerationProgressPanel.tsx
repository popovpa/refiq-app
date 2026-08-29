import { Button } from '@/shared/components/Button';
import type { PromoGenerationRun } from './types';

const ACTIVE = new Set(['queued', 'running', 'cancel_requested']);

export function GenerationProgressPanel({
  run,
  onDetails,
  onStop,
  onView,
  onRetryFailed,
}: {
  run: PromoGenerationRun;
  onDetails: () => void;
  onStop: () => void;
  onView: () => void;
  onRetryFailed?: () => void;
}) {
  const stopping = run.status === 'cancel_requested' || run.cancel_requested;
  const generating = run.items.filter((item) => item.status === 'generating').length;
  const queued = run.items.filter((item) => item.status === 'queued').length;
  const failed = run.failed_items || run.items.filter((item) => item.status === 'failed').length;
  const percentage = Math.min(100, Math.max(0, run.percentage || 0));

  if (ACTIVE.has(run.status)) {
    const extra = [
      generating ? `${generating} генерируется` : null,
      queued ? `${queued} ожидают` : null,
      failed ? `${failed} ${failed === 1 ? 'ошибка' : 'ошибки'}` : null,
    ].filter(Boolean);

    return (
      <div className="ui-card px-4 py-3 space-y-2.5">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm font-medium">
            {stopping ? 'Останавливаем генерацию…' : 'AI создаёт материалы'}
          </p>
          <p className="text-sm tabular-nums text-muted-foreground shrink-0">{percentage}%</p>
        </div>
        <ProgressBar value={percentage} />
        <p className="text-xs text-muted-foreground">
          {run.completed_items} из {run.total_items} готово · {percentage}%
          {extra.length ? ` · ${extra.join(' · ')}` : ''}
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button size="sm" variant="secondary" onClick={onDetails}>
            Подробнее
          </Button>
          {stopping ? (
            <Button size="sm" variant="ghost" disabled>
              Останавливаем…
            </Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={onStop}>
              Остановить
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (run.status === 'failed') {
    return (
      <div className="ui-card px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">
          Генерация не удалась
          {failed ? ` · ${failed} ${failed === 1 ? 'ошибка' : 'ошибки'}` : ''}
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={onDetails}>
            Подробнее
          </Button>
          {onRetryFailed && (
            <Button size="sm" variant="secondary" onClick={onRetryFailed}>
              Запустить заново
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (run.status === 'completed_with_errors') {
    return (
      <div className="ui-card px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">
          Создано {run.completed_items} из {run.total_items} материалов · {failed}{' '}
          {failed === 1 ? 'ошибка' : 'ошибки'}
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={onDetails}>
            Подробнее
          </Button>
          {onRetryFailed && (
            <Button size="sm" variant="secondary" onClick={onRetryFailed}>
              Повторить ошибку
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (run.status === 'cancelled') {
    return (
      <div className="ui-card px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">
          Генерация остановлена · создано {run.completed_items} из {run.total_items}
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={onView}>
            Посмотреть результаты
          </Button>
          {onRetryFailed && (
            <Button size="sm" variant="secondary" onClick={onRetryFailed}>
              Запустить заново
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="ui-card px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <p className="text-sm">
        Материалы созданы · {run.completed_items} из {run.total_items}
      </p>
      <Button size="sm" variant="secondary" onClick={onView}>
        Посмотреть
      </Button>
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div
      className="h-1.5 rounded-full bg-muted overflow-hidden"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      aria-label="Прогресс генерации материалов"
    >
      <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${value}%` }} />
    </div>
  );
}
