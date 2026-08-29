import { useRef, type ReactNode } from 'react';
import { Info, Upload, X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { OfferImage } from '@/shared/offers/OfferImage';
import { OfferAiFieldBadge, OfferField, OfferFormSection } from '@/shared/offers/OfferFormSection';
import {
  ACCESS_OPTIONS,
  ATTRIBUTION_MODEL_HINT,
  ATTRIBUTION_MODEL_LABEL,
  CATEGORIES,
  CONVERSION_OPTIONS,
  GEO_OPTIONS,
  TRAFFIC_TYPES,
  trafficLabel,
} from '@/shared/offers/labels';
import { DESCRIPTION_MAX, type OfferFormErrors } from '@/shared/offers/offerFormMeta';
import type { OfferFormValues } from '@/shared/offers/types';
import { resizeImage } from '@/shared/utils/image';
import { useToast } from '@/shared/components/Toast';
import { cn } from '@/shared/utils/cn';
import type { AiMarkedFields, AiRewriteField } from '@/shared/ai/types';

export function OfferForm({
  form,
  onChange,
  errors = {},
  financialWarning,
  aiMarked,
  rewriteSlot,
  imageFromWebsite,
}: {
  form: OfferFormValues;
  onChange: (next: OfferFormValues) => void;
  errors?: OfferFormErrors;
  financialWarning?: boolean;
  aiMarked?: AiMarkedFields;
  rewriteSlot?: (field: AiRewriteField) => ReactNode;
  imageFromWebsite?: boolean;
}) {
  const { addToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const set = <K extends keyof OfferFormValues>(key: K, value: OfferFormValues[K]) =>
    onChange({ ...form, [key]: value });

  const toggleTraffic = (list: 'allowed_traffic' | 'forbidden_traffic', value: string) => {
    const current = form[list];
    set(list, current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
  };

  return (
    <div className="space-y-3">
      <OfferFormSection n={1} title="Основная информация">
        <div className="grid sm:grid-cols-2 gap-3 items-start">
          <OfferField
            label="Название"
            required
            error={errors.name}
            aiMark={aiMarked?.name}
            extra={rewriteSlot?.('name')}
          >
            <input
              className={inputClass(errors.name)}
              placeholder="Например, CRM Pro"
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
            />
          </OfferField>
          <OfferField label="Категория" required aiMark={aiMarked?.category}>
            <select className="ui-input" value={form.category} onChange={(e) => set('category', e.target.value)}>
              {CATEGORIES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </OfferField>
        </div>

        <div className="grid lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-3 items-start">
          <div className="space-y-3">
            <OfferField label="Сайт продукта" aiMark={aiMarked?.product_url}>
              <input
                className="ui-input"
                placeholder="https://"
                value={form.product_url}
                onChange={(e) => set('product_url', e.target.value)}
              />
            </OfferField>
            <div>
              <div className="flex items-center justify-between gap-2 min-h-7 mb-1.5">
                <p className="text-sm font-medium text-foreground">Изображение оффера</p>
                {imageFromWebsite && form.image_url ? <OfferAiFieldBadge variant="website" /> : null}
              </div>
              <div className="rounded-lg border border-dashed border-border bg-muted/30 p-3">
                <div className="flex items-center gap-3">
                  <OfferImage src={form.image_url} name={form.name || 'Оффер'} size="lg" />
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" size="sm" variant="secondary" onClick={() => inputRef.current?.click()}>
                        <Upload size={14} />
                        {form.image_url ? 'Заменить изображение' : 'Загрузить изображение'}
                      </Button>
                      {form.image_url && (
                        <Button type="button" size="sm" variant="ghost" onClick={() => set('image_url', null)}>
                          <X size={14} />
                          Удалить
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">PNG / JPG / WEBP, рекомендуемое соотношение 1:1</p>
                  </div>
                </div>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  event.target.value = '';
                  if (!file) return;
                  if (file.size > 2 * 1024 * 1024) {
                    addToast('Файл больше 2 МБ', 'error');
                    return;
                  }
                  try {
                    set('image_url', await resizeImage(file, 240));
                  } catch {
                    addToast('Не удалось прочитать изображение', 'error');
                  }
                }}
              />
            </div>
          </div>

          <OfferField
            label="Описание"
            required
            error={errors.description}
            extra={
              <span className="flex items-center gap-2 shrink-0">
                {rewriteSlot?.('description')}
                <span className="text-xs font-medium tabular-nums text-muted-foreground whitespace-nowrap">
                  {form.description.length}/{DESCRIPTION_MAX}
                </span>
              </span>
            }
            aiMark={aiMarked?.description}
          >
            <textarea
              className={cn(inputClass(errors.description), 'min-h-[176px] h-auto py-2 resize-y')}
              placeholder="Коротко опишите продукт и что получает партнёр"
              value={form.description}
              onChange={(e) => set('description', e.target.value.slice(0, DESCRIPTION_MAX))}
            />
          </OfferField>
        </div>
      </OfferFormSection>

      <OfferFormSection n={2} title="Целевое действие и вознаграждение">
        {financialWarning && (
          <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5 text-sm">
            Изменения затронут активных партнёров. Новые условия не должны применяться задним числом.
          </div>
        )}
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3 items-start">
          <OfferField label="Тип conversion goal" required aiMark={aiMarked?.conversion_type}>
            <select
              className="ui-input"
              value={form.conversion_type}
              onChange={(e) => set('conversion_type', e.target.value)}
            >
              {CONVERSION_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </OfferField>
          <OfferField label="Модель" aiMark={aiMarked?.commission_type}>
            <select
              className="ui-input"
              value={form.commission_type}
              onChange={(e) => set('commission_type', e.target.value)}
            >
              <option value="fixed">Фиксированная сумма</option>
              <option value="percent">Процент</option>
            </select>
          </OfferField>
          <OfferField label="Размер комиссии" error={errors.commission_value} aiMark={aiMarked?.commission_value}>
            <input
              type="number"
              min="0"
              step="0.01"
              className={inputClass(errors.commission_value)}
              value={form.commission_value}
              onChange={(e) => set('commission_value', e.target.value)}
            />
          </OfferField>
          <OfferField label="Валюта" aiMark={aiMarked?.commission_currency}>
            <select
              className="ui-input"
              value={form.commission_currency}
              onChange={(e) => set('commission_currency', e.target.value)}
            >
              <option value="RUB">RUB</option>
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
            </select>
          </OfferField>
        </div>
      </OfferFormSection>

      <OfferFormSection n={3} title="Атрибуция">
        <div className="grid sm:grid-cols-2 gap-3 items-start">
          <OfferField label="Окно атрибуции (дней)" required error={errors.attribution_window_days} aiMark={aiMarked?.attribution_window_days}>
            <input
              type="number"
              min="1"
              className={inputClass(errors.attribution_window_days)}
              value={form.attribution_window_days}
              onChange={(e) => set('attribution_window_days', e.target.value)}
            />
          </OfferField>
          <OfferField
            label="Модель атрибуции"
            extra={
              <span className="inline-flex h-7 items-center text-muted-foreground cursor-help" title={ATTRIBUTION_MODEL_HINT}>
                <Info size={14} />
              </span>
            }
          >
            <div className="ui-input flex items-center text-foreground bg-muted/40">
              {ATTRIBUTION_MODEL_LABEL}
            </div>
          </OfferField>
        </div>
      </OfferFormSection>

      <OfferFormSection n={4} title="Доступ и трафик">
        <div className="grid sm:grid-cols-2 gap-3 items-start">
          <OfferField label="Тип доступа" aiMark={aiMarked?.access_policy}>
            <select
              className="ui-input"
              value={form.access_policy}
              onChange={(e) => set('access_policy', e.target.value)}
            >
              {ACCESS_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </OfferField>
          <OfferField label="GEO" aiMark={aiMarked?.geo}>
            <select className="ui-input" value={form.geo} onChange={(e) => set('geo', e.target.value)}>
              {GEO_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </OfferField>
        </div>

        <OfferField label="Разрешённый трафик" aiMark={aiMarked?.allowed_traffic}>
          <TrafficMultiSelect
            selected={form.allowed_traffic}
            onToggle={(value) => toggleTraffic('allowed_traffic', value)}
            onRemove={(value) => set('allowed_traffic', form.allowed_traffic.filter((item) => item !== value))}
          />
        </OfferField>

        <OfferField label="Запрещённый трафик" aiMark={aiMarked?.forbidden_traffic}>
          <div className="flex flex-wrap gap-1.5">
            {TRAFFIC_TYPES.map((item) => (
              <button
                key={`f-${item.value}`}
                type="button"
                onClick={() => toggleTraffic('forbidden_traffic', item.value)}
                className={cn(
                  'px-2.5 py-1 rounded-md text-xs font-medium border transition-colors',
                  form.forbidden_traffic.includes(item.value)
                    ? 'bg-red-50 text-red-700 border-red-100'
                    : 'bg-card text-muted-foreground border-border hover:text-foreground',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </OfferField>

        <OfferField
          label="Комментарий / инструкции для партнёров"
          aiMark={aiMarked?.partner_notes}
          extra={rewriteSlot?.('partner_notes')}
        >
          <textarea
            className="ui-input min-h-[72px] h-auto py-2 resize-y"
            placeholder="Необязательно"
            value={form.partner_notes}
            onChange={(e) => set('partner_notes', e.target.value)}
          />
        </OfferField>
      </OfferFormSection>
    </div>
  );
}

function TrafficMultiSelect({
  selected,
  onToggle,
  onRemove,
}: {
  selected: string[];
  onToggle: (value: string) => void;
  onRemove: (value: string) => void;
}) {
  const selectedSet = new Set(selected);
  const available = TRAFFIC_TYPES.filter((item) => !selectedSet.has(item.value));

  return (
    <div className="space-y-2">
      <div className="ui-input h-auto min-h-10 py-1.5 flex flex-wrap gap-1.5 items-center">
        {selected.length === 0 && <span className="text-sm text-muted-foreground">Выберите источники трафика</span>}
        {selected.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-accent text-primary"
          >
            {trafficLabel(value)}
            <button
              type="button"
              className="rounded-sm hover:bg-primary/10"
              onClick={() => onRemove(value)}
              aria-label={`Убрать ${trafficLabel(value)}`}
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      {available.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {available.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => onToggle(item.value)}
              className="px-2.5 py-1 rounded-md text-xs font-medium border border-border bg-card text-muted-foreground hover:text-foreground"
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function inputClass(error?: string) {
  return cn('ui-input', error && 'border-destructive focus:ring-destructive/30 focus:border-destructive');
}
