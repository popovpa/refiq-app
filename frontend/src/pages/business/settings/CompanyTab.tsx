import { useEffect, useRef, useState } from 'react';
import { Check, Upload, X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { OfferImage } from '@/shared/offers/OfferImage';
import { BUSINESS_CATEGORIES, ONBOARDING_COUNTRIES } from '@/shared/onboarding/BecomeBusinessForm';
import { resizeImage } from '@/shared/utils/image';
import { cn } from '@/shared/utils/cn';
import { useToast } from '@/shared/components/Toast';
import type { BusinessWorkspaceSettings, CompanyForm } from './types';
import { toCompanyForm, websiteHost } from './types';

type CompanyErrors = Partial<Record<keyof CompanyForm, string>>;

export function CompanyTab({
  data,
  pending,
  onSave,
}: {
  data: BusinessWorkspaceSettings;
  pending?: boolean;
  onSave: (form: CompanyForm) => void;
}) {
  const { addToast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState<CompanyForm>(() => toCompanyForm(data));
  const [errors, setErrors] = useState<CompanyErrors>({});

  useEffect(() => {
    setForm(toCompanyForm(data));
    setErrors({});
  }, [data]);

  const dirty = JSON.stringify(form) !== JSON.stringify(toCompanyForm(data));

  const set = <K extends keyof CompanyForm>(key: K, value: CompanyForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    if (errors[key]) setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const next: CompanyErrors = {};
    if (!form.name.trim()) next.name = 'Укажите название компании';
    if (!form.website.trim()) next.website = 'Укажите сайт';
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    onSave({
      ...form,
      name: form.name.trim(),
      website: form.website.trim(),
      work_email: form.work_email.trim(),
      phone: form.phone.trim(),
      description: form.description.trim(),
    });
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.7fr)_minmax(280px,1fr)]">
      <form onSubmit={handleSubmit} className="ui-card p-5 space-y-4">
        <h2 className="ui-section-title">Данные компании</h2>

        <Field id="company-name" label="Название компании" required error={errors.name}>
          <input
            id="company-name"
            className={inputClass(errors.name)}
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            autoComplete="organization"
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? 'company-name-error' : undefined}
          />
        </Field>

        <Field id="company-website" label="Сайт" required error={errors.website}>
          <input
            id="company-website"
            type="text"
            inputMode="url"
            className={inputClass(errors.website)}
            value={form.website}
            onChange={(e) => set('website', e.target.value)}
            placeholder="https://example.com"
            aria-invalid={Boolean(errors.website)}
            aria-describedby={errors.website ? 'company-website-error' : undefined}
          />
        </Field>

        <div className="grid sm:grid-cols-2 gap-3">
          <Field id="company-country" label="Страна">
            <select
              id="company-country"
              className="ui-input"
              value={form.country}
              onChange={(e) => set('country', e.target.value)}
            >
              <option value="">Не указана</option>
              {ONBOARDING_COUNTRIES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field id="company-category" label="Отрасль">
            <select
              id="company-category"
              className="ui-input"
              value={form.category}
              onChange={(e) => set('category', e.target.value)}
            >
              <option value="">Не указана</option>
              {BUSINESS_CATEGORIES.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          <Field id="company-email" label="Рабочий email">
            <input
              id="company-email"
              type="email"
              className="ui-input"
              value={form.work_email}
              onChange={(e) => set('work_email', e.target.value)}
              autoComplete="email"
            />
          </Field>
          <Field id="company-phone" label="Телефон">
            <input
              id="company-phone"
              className="ui-input"
              value={form.phone}
              onChange={(e) => set('phone', e.target.value)}
              placeholder="+7 …"
              autoComplete="tel"
            />
          </Field>
        </div>

        <Field id="company-description" label="Описание">
          <textarea
            id="company-description"
            className="ui-input min-h-[88px] h-auto py-2"
            maxLength={300}
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
          />
          <span className="text-xs text-muted-foreground">{form.description.length}/300</span>
        </Field>

        <div>
          <p className="ui-label" id="company-logo-label">
            Логотип компании
          </p>
          <div className="rounded-lg border border-dashed border-border bg-muted/30 p-3">
            <div className="flex items-center gap-3">
              <OfferImage src={form.logo_url} name={form.name || 'Компания'} size="lg" />
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    aria-labelledby="company-logo-label"
                    onClick={() => fileRef.current?.click()}
                  >
                    <Upload size={14} />
                    {form.logo_url ? 'Заменить' : 'Загрузить'}
                  </Button>
                  {form.logo_url && (
                    <Button type="button" size="sm" variant="ghost" onClick={() => set('logo_url', null)}>
                      <X size={14} />
                      Удалить
                    </Button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">PNG / JPG / WEBP</p>
              </div>
            </div>
          </div>
          <input
            ref={fileRef}
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
                set('logo_url', await resizeImage(file, 240));
              } catch {
                addToast('Не удалось прочитать изображение', 'error');
              }
            }}
          />
        </div>

        <div className="pt-1">
          <Button type="submit" disabled={pending || !dirty}>
            {pending ? 'Сохранение...' : 'Сохранить изменения'}
          </Button>
        </div>
      </form>

      <CompanyPreview form={form} />
    </div>
  );
}

function CompanyPreview({ form }: { form: CompanyForm }) {
  const host = websiteHost(form.website);
  const country = ONBOARDING_COUNTRIES.find((item) => item.value === form.country)?.label;
  const checks = [
    { key: 'basics', label: 'Основные данные', done: Boolean(form.name.trim() && (form.country || form.category)) },
    { key: 'contacts', label: 'Контакты', done: Boolean(form.work_email.trim() || form.phone.trim()) },
    { key: 'site', label: 'Сайт', done: Boolean(form.website.trim()) },
  ];

  return (
    <aside className="ui-card p-5 h-fit space-y-4">
      <h2 className="ui-section-title">Профиль компании</h2>
      <div className="flex items-center gap-3 min-w-0">
        <OfferImage src={form.logo_url} name={form.name || 'Компания'} size="lg" />
        <div className="min-w-0">
          <p className="font-semibold truncate">{form.name.trim() || 'Без названия'}</p>
          <p className="text-sm text-muted-foreground truncate">
            {[form.category || null, country || null].filter(Boolean).join(' · ') || 'Профиль компании'}
          </p>
          {host ? <p className="text-sm text-muted-foreground truncate">{host}</p> : null}
        </div>
      </div>

      {(form.work_email.trim() || form.phone.trim()) && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1.5">Контакты</p>
          {form.work_email.trim() ? <p className="text-sm truncate">{form.work_email.trim()}</p> : null}
          {form.phone.trim() ? <p className="text-sm text-muted-foreground truncate">{form.phone.trim()}</p> : null}
        </div>
      )}

      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2">Заполненность профиля</p>
        <ul className="space-y-1.5">
          {checks.map((item) => (
            <li key={item.key} className="flex items-center gap-2 text-sm">
              <span
                className={cn(
                  'inline-flex h-4 w-4 items-center justify-center rounded-full',
                  item.done ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground',
                )}
                aria-hidden="true"
              >
                <Check size={10} strokeWidth={3} />
              </span>
              <span className={item.done ? 'text-foreground' : 'text-muted-foreground'}>{item.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

function Field({
  id,
  label,
  required,
  error,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  const errorId = `${id}-error`;
  return (
    <div>
      <label htmlFor={id} className="ui-label">
        {label}
        {required ? ' *' : ''}
      </label>
      {children}
      {error ? (
        <span id={errorId} className="mt-1 block text-xs text-destructive" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

function inputClass(error?: string) {
  return cn('ui-input', error && 'border-destructive/50 focus:ring-destructive/20 focus:border-destructive/40');
}
