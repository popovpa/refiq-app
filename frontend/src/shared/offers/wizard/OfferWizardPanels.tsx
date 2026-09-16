import { Check, Clock3, Hourglass, MapPin, Percent, ShoppingCart, Target } from 'lucide-react';
import { categoryLabel } from '@/shared/catalog/categories';
import { countryByCode } from '@/shared/catalog/countries';
import { trafficSourceLabel } from '@/shared/catalog/trafficSources';
import { OfferSquareMedia } from '@/shared/offers/wizard/OfferSquareMedia';
import { accessLabel, conversionLabel } from '@/shared/offers/labels';
import { formatCommissionPrimary } from '@/shared/offers/partnerOfferCardFormat';
import type { OfferFormValues } from '@/shared/offers/types';
import { daysLabel } from '@/shared/offers/wizard/meta';
import { canPublishOffer, offerReadiness, readinessPercent, type ReadinessItem } from '@/shared/offers/wizard/readiness';
import { cn } from '@/shared/utils/cn';

function geoText(form: OfferFormValues) {
  return form.geo_countries.map((code) => countryByCode(code)?.nameRu || code).join(', ');
}

function rewardText(form: OfferFormValues) {
  if (!(Number(form.commission_value) > 0)) return '';
  const primary = formatCommissionPrimary({
    type: form.commission_type,
    value: Number(form.commission_value),
    currency: form.commission_currency,
  });
  if (form.commission_type === 'percent') {
    return form.conversion_type === 'lead' ? `${primary} с заявки` : `${primary} с продажи`;
  }
  return primary;
}

export function OfferWizardPreview({ form }: { form: OfferFormValues }) {
  const reward = rewardText(form);
  return (
    <div className="ui-card w-full space-y-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="ui-section-title whitespace-nowrap">Предпросмотр оффера</h2>
        <span className="ui-badge shrink-0 bg-muted text-muted-foreground">Черновик</span>
      </div>
      <OfferSquareMedia src={form.image_url} className="mx-auto max-w-[168px]" />
      <div>
        <p className={cn('font-semibold text-sm', !form.name.trim() && 'text-muted-foreground')}>
          {form.name.trim() || 'Название оффера'}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">{form.category ? categoryLabel(form.category) : 'Категория'}</p>
      </div>
      <p className="text-xs text-muted-foreground line-clamp-3">
        {form.description.trim() || 'Описание появится здесь.'}
      </p>
      {form.product_url && (
        <p className="text-xs text-primary truncate">{form.product_url.replace(/^https?:\/\//, '')}</p>
      )}
      {form.geo_countries.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {form.geo_countries.map((code) => (
            <span key={code} className="ui-badge bg-accent text-primary">
              {countryByCode(code)?.nameRu || code}
            </span>
          ))}
        </div>
      )}
      {form.allowed_traffic.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {form.allowed_traffic.map((code) => (
            <span key={code} className="ui-badge bg-accent text-primary">
              {trafficSourceLabel(code)}
            </span>
          ))}
        </div>
      )}
      <dl className="space-y-1.5 text-xs">
        <PreviewRow label="Статус" value="Черновик" />
        <PreviewRow label="Доступ" value={accessLabel(form.access_policy)} />
        {reward && <PreviewRow label="Вознаграждение" value={reward} />}
      </dl>
    </div>
  );
}

export function OfferWizardReadiness({ form, current }: { form: OfferFormValues; current: ReadinessItem['id'] }) {
  const items = offerReadiness(form, current);
  const percent = current === 'review' && canPublishOffer(form) ? 100 : Math.max(readinessPercent(form), current === 'basics' ? 25 : current === 'traffic' ? 50 : current === 'conversions' ? 75 : 100);
  const ready = current === 'review' && canPublishOffer(form);

  return (
    <div className="ui-card w-full space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h2 className="ui-section-title">Готовность оффера</h2>
        <span className="text-sm font-semibold text-primary">{ready ? 'Готов к публикации' : `${percent}%`}</span>
      </div>
      {!ready && (
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div className="h-full bg-primary rounded-full" style={{ width: `${percent}%` }} />
        </div>
      )}
      <ul className="space-y-2 text-sm">
        {items.map((item, index) => (
          <li key={item.id} className="flex items-start gap-2">
            <span
              className={cn(
                'mt-0.5 h-5 w-5 rounded-full flex items-center justify-center text-[11px] font-semibold shrink-0',
                item.done ? 'bg-primary text-primary-foreground' : item.current ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
              )}
            >
              {item.done && !item.current ? <Check size={12} /> : index + 1}
            </span>
            <span>
              <span className={item.current ? 'font-medium' : item.done ? 'text-foreground' : 'text-muted-foreground'}>
                {item.label}
              </span>
              <span className="block text-xs text-muted-foreground">
                {item.done && !item.current ? 'Завершено' : item.current ? 'Текущий шаг' : 'Ожидает заполнения'}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OfferReviewPreview({
  form,
  onEdit,
}: {
  form: OfferFormValues;
  onEdit: (step: 'basics' | 'traffic' | 'conversions') => void;
}) {
  const reward = rewardText(form) || '—';
  return (
    <div className="space-y-3">
      <div className="ui-card flex gap-4 p-4">
        <OfferSquareMedia src={form.image_url} className="w-24 shrink-0" />
        <div className="min-w-0 space-y-2">
          <div>
            <h2 className="text-lg font-semibold leading-tight">{form.name || 'Название оффера'}</h2>
            <p className="text-sm text-muted-foreground">{form.category ? categoryLabel(form.category) : '—'}</p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm">
            <span className="inline-flex items-center gap-1.5">
              <MapPin size={14} className="text-primary" />
              <span>
                <span className="block text-[11px] text-muted-foreground">География</span>
                {geoText(form) || '—'}
              </span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Percent size={14} className="text-primary" />
              <span>
                <span className="block text-[11px] text-muted-foreground">Вознаграждение</span>
                {reward}
              </span>
            </span>
          </div>
        </div>
      </div>

      <ReviewCard title="О продукте" onEdit={() => onEdit('basics')}>
        <p className="text-sm whitespace-pre-wrap">{form.description || '—'}</p>
      </ReviewCard>

      <ReviewCard title="Параметры трафика" onEdit={() => onEdit('traffic')}>
        <div className="grid sm:grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Политика доступа</p>
            <p className="font-medium">{accessLabel(form.access_policy)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">География</p>
            <p className="font-medium">{geoText(form) || '—'}</p>
          </div>
        </div>
        <div className="mt-3">
          <p className="text-xs text-muted-foreground mb-1.5">Разрешённые источники трафика</p>
          <div className="flex flex-wrap gap-1.5">
            {form.allowed_traffic.map((code) => (
              <span key={code} className="ui-badge bg-accent text-primary">
                {trafficSourceLabel(code)}
              </span>
            ))}
          </div>
        </div>
      </ReviewCard>

      <ReviewCard title="Параметры конверсии" onEdit={() => onEdit('conversions')}>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Summary icon={ShoppingCart} label="Целевое действие" value={conversionLabel(form.conversion_type)} />
          <Summary icon={Percent} label="Вознаграждение" value={reward} />
          <Summary icon={Clock3} label="Окно атрибуции" value={daysLabel(Number(form.attribution_window_days) || 0)} />
          <Summary icon={Hourglass} label="Холд-период" value={daysLabel(Number(form.hold_period_days) || 0)} />
        </div>
      </ReviewCard>
    </div>
  );
}

function ReviewCard({ title, onEdit, children }: { title: string; onEdit: () => void; children: React.ReactNode }) {
  return (
    <div className="ui-card p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <h3 className="ui-section-title">{title}</h3>
        <button type="button" className="text-sm text-primary hover:underline" onClick={onEdit}>
          Редактировать
        </button>
      </div>
      {children}
    </div>
  );
}

function Summary({ icon: Icon, label, value }: { icon: typeof Target; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 px-3 py-2">
      <p className="text-[11px] text-muted-foreground inline-flex items-center gap-1">
        <Icon size={12} className="text-primary" />
        {label}
      </p>
      <p className="font-medium text-sm mt-1">{value}</p>
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
