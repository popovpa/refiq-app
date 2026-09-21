import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import { BUSINESS_ORG_TYPES, ONBOARDING_COUNTRIES } from '@/shared/onboarding/constants';
import type { OrgOnboardingForm } from '@/shared/onboarding/flow';
import type { OrgFormErrors } from '@/shared/onboarding/validation';

export function OnboardingOrgForm({
  form,
  errors,
  context,
  pending,
  onChange,
  onSave,
  onSearchAnother,
}: {
  form: OrgOnboardingForm;
  errors: OrgFormErrors;
  context: 'business' | 'partner';
  pending?: boolean;
  onChange: (patch: Partial<OrgOnboardingForm>) => void;
  onSave: () => void;
  onSearchAnother: () => void;
}) {
  const types = context === 'partner'
    ? [
        { value: 'SOLE_PROPRIETOR', label: 'ИП' },
        { value: 'LEGAL_ENTITY', label: 'Юридическое лицо' },
      ]
    : BUSINESS_ORG_TYPES;

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Основные данные</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Тип организации" error={errors.subject_type}>
            <select className={inputClass(errors.subject_type)} value={form.subject_type} onChange={(e) => onChange({ subject_type: e.target.value })}>
              {types.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Страна регистрации" error={errors.country}>
            <select className={inputClass(errors.country)} value={form.country} onChange={(e) => onChange({ country: e.target.value })}>
              {ONBOARDING_COUNTRIES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Полное юридическое наименование" error={errors.legal_name} className="sm:col-span-2">
            <input className={inputClass(errors.legal_name)} value={form.legal_name} onChange={(e) => onChange({ legal_name: e.target.value })} />
          </Field>
          <Field label="ИНН" error={errors.inn}>
            <input className={inputClass(errors.inn)} inputMode="numeric" value={form.inn} onChange={(e) => onChange({ inn: e.target.value })} />
          </Field>
          {form.subject_type === 'SOLE_PROPRIETOR' ? (
            <Field label="ОГРНИП" error={errors.ogrnip}>
              <input className={inputClass(errors.ogrnip)} inputMode="numeric" value={form.ogrnip} onChange={(e) => onChange({ ogrnip: e.target.value })} />
            </Field>
          ) : (
            <Field label="ОГРН" error={errors.ogrn}>
              <input className={inputClass(errors.ogrn)} inputMode="numeric" value={form.ogrn} onChange={(e) => onChange({ ogrn: e.target.value })} />
            </Field>
          )}
          <Field label="Юридический адрес" error={errors.legal_address} className="sm:col-span-2">
            <textarea className={cn(inputClass(errors.legal_address), 'min-h-[72px] h-auto py-2')} value={form.legal_address} onChange={(e) => onChange({ legal_address: e.target.value })} />
          </Field>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Контактные данные</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={context === 'business' ? 'ФИО контактного лица' : 'ФИО контактного лица'} error={errors.contact_name} className={context === 'business' ? '' : 'sm:col-span-2'}>
            <input className={inputClass(errors.contact_name)} value={form.contact_name} onChange={(e) => onChange({ contact_name: e.target.value })} />
          </Field>
          {context === 'business' ? (
            <Field label="Должность" error={errors.job_title}>
              <input className={inputClass(errors.job_title)} value={form.job_title} onChange={(e) => onChange({ job_title: e.target.value })} />
            </Field>
          ) : null}
          <Field label={context === 'business' ? 'Рабочий email' : 'Email'} error={errors.work_email}>
            <input type="email" className={inputClass(errors.work_email)} value={form.work_email} onChange={(e) => onChange({ work_email: e.target.value })} />
          </Field>
          <Field label="Телефон" error={errors.phone}>
            <input className={inputClass(errors.phone)} value={form.phone} onChange={(e) => onChange({ phone: e.target.value })} />
          </Field>
        </div>
      </section>

      {context === 'business' ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Сайт</h2>
          <Field label="Сайт / основной домен" error={errors.website}>
            <input className={inputClass(errors.website)} value={form.website} onChange={(e) => onChange({ website: e.target.value })} />
          </Field>
        </section>
      ) : null}

      <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-1">
        <Button type="button" variant="secondary" disabled={pending} onClick={onSearchAnother}>
          Найти другую организацию
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? 'Сохранение...' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  error,
  className,
  children,
}: {
  label: string;
  error?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={cn('block min-w-0', className)}>
      <span className="ui-label">{label}</span>
      {children}
      {error ? <span className="mt-1 block text-xs text-destructive">{error}</span> : null}
    </label>
  );
}

function inputClass(error?: string) {
  return cn('ui-input', error && 'border-destructive/50 focus:ring-destructive/20 focus:border-destructive/40');
}
