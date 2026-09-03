import { Check, Sparkles } from 'lucide-react';
import { OfferImage } from '@/shared/offers/OfferImage';
import { accessLabel, conversionLabel, trafficLabel } from '@/shared/offers/labels';
import { formatCommissionPrimary } from '@/shared/offers/partnerOfferCardFormat';
import type { OfferFormValues } from '@/shared/offers/types';
import { missingRecommended, offerReadiness } from '@/shared/offers/wizard/readiness';
import { cn } from '@/shared/utils/cn';

export function OfferWizardPreview({ form }: { form: OfferFormValues }) {
  const reward =
    Number(form.commission_value) > 0
      ? formatCommissionPrimary({
          type: form.commission_type,
          value: Number(form.commission_value),
          currency: form.commission_currency,
        })
      : null;

  return (
    <div className="ui-card p-4 space-y-4">
      <h2 className="ui-section-title">Как увидит партнёр</h2>
      <div className="flex items-start gap-3">
        <OfferImage src={form.image_url} name={form.name || 'Оффер'} size="lg" />
        <div className="min-w-0">
          <p className={cn('font-semibold', !form.name.trim() && 'text-muted-foreground')}>
            {form.name.trim() || 'Название оффера'}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">{form.category || 'Категория'}</p>
        </div>
      </div>
      {reward && (
        <p className="text-lg font-semibold text-primary">
          {reward}
          <span className="block text-xs font-normal text-muted-foreground mt-0.5">
            за {conversionLabel(form.conversion_type).toLowerCase()}
          </span>
        </p>
      )}
      <dl className="space-y-2 text-sm">
        <PreviewRow label="GEO" value={form.geo || '—'} />
        <PreviewRow label="Атрибуция" value={`${form.attribution_window_days || '—'} дн.`} />
        <PreviewRow label="Доступ" value={accessLabel(form.access_policy)} />
        <PreviewRow label="Источники" value={form.allowed_traffic.map(trafficLabel).join(' · ') || '—'} />
      </dl>
      {form.forbidden_traffic.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Ограничения: {form.forbidden_traffic.map(trafficLabel).join(', ')}
        </p>
      )}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1">Описание</p>
        <p className="text-sm whitespace-pre-wrap">{form.description.trim() || 'Описание появится здесь.'}</p>
      </div>
    </div>
  );
}

export function OfferWizardReadiness({
  form,
  onFillMissing,
  fillPending,
}: {
  form: OfferFormValues;
  onFillMissing?: () => void;
  fillPending?: boolean;
}) {
  const items = offerReadiness(form);
  const required = items.filter((item) => item.required);
  const recommended = missingRecommended(form);
  const ready = required.every((item) => item.done);

  return (
    <div className="ui-card p-4 space-y-3">
      <h2 className="ui-section-title">{ready ? 'Оффер почти готов' : 'Готовность оффера'}</h2>
      <ul className="space-y-1.5 text-sm">
        {items.map((item) => (
          <li key={item.id} className="flex items-start gap-2">
            <span
              className={cn(
                'mt-0.5',
                item.done ? 'text-success' : item.required ? 'text-warning' : 'text-muted-foreground',
              )}
            >
              {item.done ? <Check size={14} /> : item.required ? '○' : '⚠'}
            </span>
            <span className={item.done ? 'text-foreground' : 'text-muted-foreground'}>{item.label}</span>
          </li>
        ))}
      </ul>
      {recommended.length > 0 && onFillMissing && (
        <button
          type="button"
          disabled={fillPending}
          onClick={onFillMissing}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline disabled:opacity-50"
        >
          <Sparkles size={12} />
          {fillPending ? 'Заполняем...' : 'Заполнить недостающее с AI'}
        </button>
      )}
      <p className="text-[11px] text-muted-foreground">
        Черновик можно сохранить и вернуться позже. Публикация доступна после обязательных полей.
      </p>
    </div>
  );
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-right">{value}</dd>
    </div>
  );
}
