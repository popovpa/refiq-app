import { useEffect, useState } from 'react';
import { Info } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { ACCESS_OPTIONS } from '@/shared/offers/labels';
import type { BusinessWorkspaceSettings, DefaultsForm } from './types';
import { toDefaultsForm } from './types';

const ATTRIBUTION_HINT =
  'Период после допустимого партнёрского взаимодействия, в течение которого конверсия может быть засчитана партнёру.';

export function DefaultsTab({
  data,
  pending,
  onSave,
}: {
  data: BusinessWorkspaceSettings;
  pending?: boolean;
  onSave: (form: DefaultsForm) => void;
}) {
  const [form, setForm] = useState<DefaultsForm>(() => toDefaultsForm(data));

  useEffect(() => {
    setForm(toDefaultsForm(data));
  }, [data]);

  const dirty = JSON.stringify(form) !== JSON.stringify(toDefaultsForm(data));

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSave(form);
  };

  return (
    <form onSubmit={handleSubmit} className="ui-card p-5 space-y-4">
      <div>
        <h2 className="ui-section-title">Настройки по умолчанию</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Эти значения будут автоматически использоваться при создании новых офферов.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        <Field id="default-currency" label="Валюта">
          <select
            id="default-currency"
            className="ui-input"
            value={form.currency}
            onChange={(e) => setForm({ ...form, currency: e.target.value })}
          >
            <option value="RUB">RUB</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
        </Field>

        <Field
          id="default-attribution"
          label="Окно атрибуции"
          extra={
            <span className="text-muted-foreground cursor-help" title={ATTRIBUTION_HINT}>
              <Info size={14} aria-label={ATTRIBUTION_HINT} />
            </span>
          }
        >
          <div className="flex items-center gap-2">
            <input
              id="default-attribution"
              type="number"
              min="1"
              max="365"
              className="ui-input"
              value={form.default_attribution_window_days}
              onChange={(e) => setForm({ ...form, default_attribution_window_days: e.target.value })}
            />
            <span className="text-sm text-muted-foreground shrink-0">дней</span>
          </div>
        </Field>

        <Field id="default-access" label="Тип доступа">
          <select
            id="default-access"
            className="ui-input"
            value={form.default_access_policy}
            onChange={(e) => setForm({ ...form, default_access_policy: e.target.value })}
          >
            {ACCESS_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>

        <Field
          id="default-confirmation"
          label="Период подтверждения конверсии"
          hint="Сколько времени конверсия может ожидать окончательного подтверждения."
        >
          <div className="flex items-center gap-2">
            <input
              id="default-confirmation"
              type="number"
              min="0"
              max="365"
              className="ui-input"
              value={form.default_confirmation_days}
              onChange={(e) => setForm({ ...form, default_confirmation_days: e.target.value })}
            />
            <span className="text-sm text-muted-foreground shrink-0">дней</span>
          </div>
        </Field>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-1">
        <p className="text-xs text-muted-foreground">ⓘ Изменения применяются только к новым офферам.</p>
        <Button type="submit" disabled={pending || !dirty}>
          {pending ? 'Сохранение...' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

function Field({
  id,
  label,
  extra,
  hint,
  children,
}: {
  id: string;
  label: string;
  extra?: React.ReactNode;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <label htmlFor={id} className="ui-label mb-0">
          {label}
        </label>
        {extra}
      </div>
      {children}
      {hint ? <p className="mt-1.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
