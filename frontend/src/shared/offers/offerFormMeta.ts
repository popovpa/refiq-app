import type { OfferFormValues } from '@/shared/offers/types';

export const OFFER_TEXT_MAX = 3000;
export const DESCRIPTION_MAX = OFFER_TEXT_MAX;
export const PARTNER_NOTES_MAX = OFFER_TEXT_MAX;

export type OfferFormErrorKey =
  | 'name'
  | 'description'
  | 'partner_notes'
  | 'category'
  | 'access_policy'
  | 'geo_countries'
  | 'allowed_traffic'
  | 'conversion_type'
  | 'commission_value'
  | 'attribution_window_days'
  | 'hold_period_days';
export type OfferFormErrors = Partial<Record<OfferFormErrorKey, string>>;

export type CompletenessSection = {
  id: string;
  label: string;
  filled: number;
  total: number;
};

const HOLD_VALUES = new Set(['0', '3', '7', '14', '30']);

export function offerFormErrors(form: OfferFormValues, requireCommission: boolean): OfferFormErrors {
  const errors: OfferFormErrors = {};
  if (!form.name.trim()) errors.name = 'Укажите название оффера';
  if (!form.category.trim()) errors.category = 'Выберите категорию';
  if (!form.description.trim()) errors.description = 'Укажите описание оффера';
  else if (form.description.trim().length > DESCRIPTION_MAX) {
    errors.description = 'Максимальная длина — 3000 символов';
  }
  if (form.partner_notes.trim().length > PARTNER_NOTES_MAX) {
    errors.partner_notes = 'Максимальная длина — 3000 символов';
  }
  if (!form.access_policy) errors.access_policy = 'Выберите политику доступа';
  if (form.geo_countries.length === 0) errors.geo_countries = 'Выберите хотя бы одну страну';
  if (form.allowed_traffic.length === 0) errors.allowed_traffic = 'Выберите хотя бы один разрешённый источник трафика';
  if (!form.conversion_type) errors.conversion_type = 'Выберите целевое действие';
  if (requireCommission) {
    const value = Number(form.commission_value);
    if (!(value > 0)) {
      errors.commission_value = 'Укажите размер комиссии';
    } else if (form.commission_type === 'percent' && value > 100) {
      errors.commission_value = 'Укажите размер комиссии';
    }
  }
  if (!Number(form.attribution_window_days) || Number(form.attribution_window_days) < 1) {
    errors.attribution_window_days = 'Укажите окно атрибуции';
  }
  if (!HOLD_VALUES.has(String(form.hold_period_days))) {
    errors.hold_period_days = 'Выберите холд-период';
  }
  return errors;
}

export function stepErrors(form: OfferFormValues, step: 'basics' | 'traffic' | 'conversions'): OfferFormErrors {
  const all = offerFormErrors(form, true);
  if (step === 'basics') {
    return pick(all, ['name', 'category', 'description', 'partner_notes', 'access_policy']);
  }
  if (step === 'traffic') {
    return pick(all, ['geo_countries', 'allowed_traffic']);
  }
  return pick(all, ['conversion_type', 'commission_value', 'attribution_window_days', 'hold_period_days']);
}

export function canSubmitOffer(form: OfferFormValues, requireCommission: boolean): boolean {
  return Object.keys(offerFormErrors(form, requireCommission)).length === 0;
}

export function offerCompleteness(form: OfferFormValues): CompletenessSection[] {
  return [
    {
      id: 'main',
      label: 'Основная информация',
      filled: count([Boolean(form.name.trim()), Boolean(form.category), Boolean(form.description.trim()), Boolean(form.image_url)]),
      total: 4,
    },
    {
      id: 'reward',
      label: 'Вознаграждение',
      filled: count([
        Boolean(form.conversion_type),
        Boolean(form.commission_type),
        Number(form.commission_value) > 0,
        Boolean(form.commission_currency),
      ]),
      total: 4,
    },
    {
      id: 'attribution',
      label: 'Атрибуция',
      filled: count([Number(form.attribution_window_days) >= 1, HOLD_VALUES.has(String(form.hold_period_days))]),
      total: 2,
    },
    {
      id: 'access',
      label: 'Доступ и трафик',
      filled: count([Boolean(form.access_policy), form.allowed_traffic.length > 0, form.geo_countries.length > 0]),
      total: 3,
    },
  ];
}

function pick(errors: OfferFormErrors, keys: OfferFormErrorKey[]): OfferFormErrors {
  const next: OfferFormErrors = {};
  keys.forEach((key) => {
    const value = errors[key];
    if (value) next[key] = value;
  });
  return next;
}

function count(flags: boolean[]): number {
  return flags.filter(Boolean).length;
}
