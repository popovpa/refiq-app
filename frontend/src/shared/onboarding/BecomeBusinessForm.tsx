import { useState } from 'react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import type { ActivateBusinessPayload } from '@/shared/api/roles';

export const ONBOARDING_COUNTRIES = [
  { value: 'RU', label: 'Россия' },
  { value: 'KZ', label: 'Казахстан' },
  { value: 'BY', label: 'Беларусь' },
  { value: 'UA', label: 'Украина' },
  { value: 'US', label: 'Соединённые Штаты' },
  { value: 'GB', label: 'Великобритания' },
  { value: 'DE', label: 'Германия' },
  { value: 'TR', label: 'Турция' },
];

export const BUSINESS_CATEGORIES = [
  'SaaS',
  'Fintech',
  'Education',
  'E-commerce',
  'Marketing',
  'Услуги',
  'Other',
];

type FormState = {
  name: string;
  website: string;
  country: string;
  category: string;
  work_email: string;
  phone: string;
  description: string;
};

type FormErrors = Partial<Record<keyof FormState, string>>;

const emptyForm = (defaults?: Partial<FormState>): FormState => ({
  name: defaults?.name || '',
  website: defaults?.website || '',
  country: defaults?.country || 'RU',
  category: defaults?.category || '',
  work_email: defaults?.work_email || '',
  phone: defaults?.phone || '',
  description: defaults?.description || '',
});

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {};
  if (!form.name.trim()) errors.name = 'Укажите название компании';
  if (!form.website.trim()) errors.website = 'Укажите веб-сайт';
  if (!form.country) errors.country = 'Выберите страну';
  if (!form.category) errors.category = 'Выберите категорию';
  if (!form.work_email.trim()) errors.work_email = 'Укажите рабочий email';
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.work_email.trim())) {
    errors.work_email = 'Некорректный email';
  }
  if (!form.phone.trim()) errors.phone = 'Укажите телефон';
  else if (form.phone.trim().length < 5) errors.phone = 'Слишком короткий телефон';
  return errors;
}

export function BecomeBusinessForm({
  defaults,
  pending,
  submitLabel = 'Стать бизнесом',
  onSubmit,
}: {
  defaults?: Partial<FormState>;
  pending?: boolean;
  submitLabel?: string;
  onSubmit: (payload: ActivateBusinessPayload) => void;
}) {
  const [form, setForm] = useState<FormState>(() => emptyForm(defaults));
  const [errors, setErrors] = useState<FormErrors>({});

  const set = (key: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    if (errors[key]) setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    onSubmit({
      name: form.name.trim(),
      website: form.website.trim(),
      country: form.country,
      category: form.category,
      work_email: form.work_email.trim(),
      phone: form.phone.trim(),
      description: form.description.trim() || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field label="Название компании / бренда" error={errors.name} required>
        <input
          className={inputClass(errors.name)}
          value={form.name}
          onChange={(e) => set('name', e.target.value)}
          placeholder="Acme"
        />
      </Field>
      <Field label="Веб-сайт" error={errors.website} required>
        <input
          className={inputClass(errors.website)}
          value={form.website}
          onChange={(e) => set('website', e.target.value)}
          placeholder="https://example.com"
        />
      </Field>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Страна" error={errors.country} required>
          <select
            className={inputClass(errors.country)}
            value={form.country}
            onChange={(e) => set('country', e.target.value)}
          >
            {ONBOARDING_COUNTRIES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Категория / отрасль" error={errors.category} required>
          <select
            className={inputClass(errors.category)}
            value={form.category}
            onChange={(e) => set('category', e.target.value)}
          >
            <option value="">Выберите</option>
            {BUSINESS_CATEGORIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Рабочий email" error={errors.work_email} required>
        <input
          type="email"
          className={inputClass(errors.work_email)}
          value={form.work_email}
          onChange={(e) => set('work_email', e.target.value)}
        />
      </Field>
      <Field label="Телефон" error={errors.phone} required>
        <input
          className={inputClass(errors.phone)}
          value={form.phone}
          onChange={(e) => set('phone', e.target.value)}
          placeholder="+7 999 000-00-00"
        />
      </Field>
      <Field label="Краткое описание бизнеса">
        <textarea
          className="ui-input min-h-[80px] h-auto py-2"
          maxLength={300}
          value={form.description}
          onChange={(e) => set('description', e.target.value)}
        />
        <span className="text-xs text-muted-foreground">{form.description.length}/300</span>
      </Field>
      <Button type="submit" className="w-full" size="lg" disabled={pending}>
        {pending ? 'Подключение...' : submitLabel}
      </Button>
    </form>
  );
}

function Field({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="ui-label">
        {label}
        {required ? ' *' : ''}
      </span>
      {children}
      {error && <span className="mt-1 block text-xs text-destructive">{error}</span>}
    </label>
  );
}

function inputClass(error?: string) {
  return cn('ui-input', error && 'border-destructive/50 focus:ring-destructive/20 focus:border-destructive/40');
}
