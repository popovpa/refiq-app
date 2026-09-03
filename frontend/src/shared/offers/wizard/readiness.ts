import type { OfferFormValues } from '@/shared/offers/types';

export type ReadinessItem = {
  id: string;
  label: string;
  required: boolean;
  done: boolean;
};

export function offerReadiness(form: OfferFormValues): ReadinessItem[] {
  const commissionValue = Number(form.commission_value);
  const commissionOk =
    form.commission_type === 'percent'
      ? commissionValue > 0 && commissionValue <= 100
      : commissionValue > 0;

  return [
    {
      id: 'name_desc',
      label: 'Название и описание',
      required: true,
      done: Boolean(form.name.trim() && form.description.trim()),
    },
    { id: 'category', label: 'Категория', required: true, done: Boolean(form.category.trim()) },
    {
      id: 'reward',
      label: 'Вознаграждение',
      required: true,
      done: Boolean(form.conversion_type && form.commission_type && commissionOk),
    },
    {
      id: 'attribution',
      label: 'Атрибуция',
      required: true,
      done: Number(form.attribution_window_days) >= 1,
    },
    { id: 'geo', label: 'GEO', required: true, done: Boolean(form.geo.trim()) },
    { id: 'traffic', label: 'Источники трафика', required: true, done: form.allowed_traffic.length > 0 },
    { id: 'image', label: 'Изображение', required: false, done: Boolean(form.image_url) },
    { id: 'product_url', label: 'Сайт продукта', required: false, done: Boolean(form.product_url.trim()) },
  ];
}

export function canPublishOffer(form: OfferFormValues): boolean {
  return offerReadiness(form).filter((item) => item.required).every((item) => item.done);
}

export function missingRecommended(form: OfferFormValues): ReadinessItem[] {
  return offerReadiness(form).filter((item) => !item.required && !item.done);
}
