import { Info } from 'lucide-react';
import { OfferImage } from '@/shared/offers/OfferImage';
import { conversionLabel, statusBadge } from '@/shared/offers/labels';
import { formatCommissionPrimary } from '@/shared/offers/partnerOfferCardFormat';
import { offerCompleteness } from '@/shared/offers/offerFormMeta';
import type { OfferFormValues } from '@/shared/offers/types';
import { cn } from '@/shared/utils/cn';

export function OfferFormSidebar({
  form,
  status,
}: {
  form: OfferFormValues;
  status?: string | null;
}) {
  const sections = offerCompleteness(form);
  const filled = sections.reduce((sum, item) => sum + item.filled, 0);
  const total = sections.reduce((sum, item) => sum + item.total, 0);
  const badge = status ? statusBadge(status) : null;
  const reward =
    Number(form.commission_value) > 0
      ? formatCommissionPrimary({
          type: form.commission_type,
          value: Number(form.commission_value),
          currency: form.commission_currency,
        })
      : '—';

  return (
    <div className="space-y-3">
      <div className="ui-card p-4 space-y-3">
        <h2 className="ui-section-title">Предпросмотр оффера</h2>
        <div className="flex items-start gap-3">
          <OfferImage src={form.image_url} name={form.name || 'Оффер'} size="lg" />
          <div className="min-w-0">
            <p className={cn('text-sm font-semibold truncate', !form.name.trim() && 'text-muted-foreground')}>
              {form.name.trim() || 'Название оффера'}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{form.category || 'Категория'}</p>
          </div>
        </div>
        <dl className="space-y-1.5 text-sm">
          <PreviewRow label="Конверсия" value={conversionLabel(form.conversion_type)} />
          <PreviewRow label="Вознаграждение" value={reward} />
          <PreviewRow
            label="Модель"
            value={form.commission_type === 'percent' ? 'Процент' : 'Фиксированная сумма'}
          />
          <PreviewRow
            label="Окно атрибуции"
            value={Number(form.attribution_window_days) >= 1 ? `${form.attribution_window_days} дн.` : '—'}
          />
        </dl>
      </div>

      <div className="ui-card p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="ui-section-title">{status ? 'Статус и заполненность' : 'Заполненность оффера'}</h2>
          {badge && <span className={cn('ui-badge', badge.className)}>{badge.label}</span>}
        </div>
        <p className="text-xs text-muted-foreground">
          {status
            ? completenessHint(status, filled, total)
            : 'Чтобы опубликовать оффер и сделать его доступным партнёрам, нужно заполнить обязательные поля.'}
        </p>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${Math.round((filled / Math.max(total, 1)) * 100)}%` }}
          />
        </div>
        <ul className="space-y-1.5">
          {sections.map((section) => (
            <li key={section.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="text-muted-foreground">{section.label}</span>
              <span
                className={cn(
                  'tabular-nums',
                  section.filled === section.total ? 'text-foreground' : 'text-muted-foreground',
                )}
              >
                {section.filled}/{section.total}
              </span>
            </li>
          ))}
        </ul>
        {(!status || status === 'draft') && (
          <p className="text-[11px] text-muted-foreground inline-flex items-start gap-1.5">
            <Info size={12} className="mt-0.5 shrink-0" />
            Черновик можно сохранить и доработать позже.
          </p>
        )}
      </div>
    </div>
  );
}

function completenessHint(status: string, filled: number, total: number) {
  if (status === 'draft') {
    return filled === total
      ? 'Оффер заполнен и готов к публикации.'
      : 'Чтобы опубликовать оффер и сделать его доступным партнёрам, нужно заполнить обязательные поля.';
  }
  return 'Проверьте условия перед сохранением. Изменения не применяются задним числом.';
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-muted-foreground shrink-0">{label}</dt>
      <dd className="text-right font-medium min-w-0 break-words">{value}</dd>
    </div>
  );
}
