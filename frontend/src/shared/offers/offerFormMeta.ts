import type { OfferFormValues } from '@/shared/offers/types';

export const DESCRIPTION_MAX = 1000;

export type OfferFormErrorKey =
  | 'name'
  | 'description'
  | 'commission_value'
  | 'attribution_window_days';
export type OfferFormErrors = Partial<Record<OfferFormErrorKey, string>>;

export type CompletenessSection = {
  id: string;
  label: string;
  filled: number;
  total: number;
};

export function offerFormErrors(form: OfferFormValues, requireCommission: boolean): OfferFormErrors {
  const errors: OfferFormErrors = {};
  if (!form.name.trim()) errors.name = 'Укажите название';
  if (!form.description.trim()) errors.description = 'Добавьте описание';
  if (requireCommission) {
    const value = Number(form.commission_value);
    if (!(value > 0)) {
      errors.commission_value = 'Укажите размер вознаграждения';
    } else if (form.commission_type === 'percent' && value > 100) {
      errors.commission_value = 'Процент не может быть больше 100';
    }
  }
  if (!Number(form.attribution_window_days) || Number(form.attribution_window_days) < 1) {
    errors.attribution_window_days = 'Укажите срок закрепления клиента';
  }
  return errors;
}

export function canSubmitOffer(form: OfferFormValues, requireCommission: boolean): boolean {
  return Object.keys(offerFormErrors(form, requireCommission)).length === 0;
}

export function offerCompleteness(form: OfferFormValues): CompletenessSection[] {
  return [
    {
      id: 'main',
      label: 'Основная информация',
      filled: count([
        Boolean(form.name.trim()),
        Boolean(form.category),
        Boolean(form.description.trim()),
        Boolean(form.image_url),
      ]),
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
      filled: count([Number(form.attribution_window_days) >= 1, true]),
      total: 2,
    },
    {
      id: 'access',
      label: 'Доступ и трафик',
      filled: count([Boolean(form.access_policy), form.allowed_traffic.length > 0]),
      total: 2,
    },
  ];
}

function count(flags: boolean[]): number {
  return flags.filter(Boolean).length;
}
