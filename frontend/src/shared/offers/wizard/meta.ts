import type { OfferFormValues } from '@/shared/offers/types';

export const WIZARD_STEPS = [
  { id: 'basics', label: 'Основное' },
  { id: 'traffic', label: 'Трафик' },
  { id: 'conversions', label: 'Конверсии' },
  { id: 'review', label: 'Проверка' },
] as const;

export type WizardStepId = (typeof WIZARD_STEPS)[number]['id'];

export const CONVERSION_GOAL_CARDS = [
  {
    value: 'sale',
    title: 'Покупка',
    description: 'Партнёр получает вознаграждение за подтверждённую покупку.',
  },
  {
    value: 'lead',
    title: 'Заявка',
    description: 'Партнёр получает вознаграждение за подтверждённую заявку.',
  },
] as const;

export const ACCESS_CARDS = [
  {
    value: 'open',
    title: 'Всем партнёрам',
    description: 'Оффер виден всем партнёрам, и они могут сразу начать продвижение.',
  },
  {
    value: 'approval',
    title: 'После одобрения',
    description: 'Партнёры смогут продвигать оффер после вашей модерации.',
  },
  {
    value: 'invite_only',
    title: 'По приглашению',
    description: 'Оффер доступен только приглашённым партнёрам.',
  },
] as const;

export const ATTRIBUTION_PRESETS = [7, 14, 30, 60, 90] as const;
export const HOLD_PRESETS = [0, 3, 7, 14, 30] as const;

export function daysLabel(days: number): string {
  const mod10 = days % 10;
  const mod100 = days % 100;
  if (mod10 === 1 && mod100 !== 11) return `${days} день`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${days} дня`;
  return `${days} дней`;
}

export function commissionExample(form: OfferFormValues): string | null {
  const value = Number(form.commission_value);
  if (!(value > 0)) return null;
  if (form.commission_type === 'percent') {
    const payout = Math.round((20000 * value) / 100);
    return `При продаже на 20 000 ₽ партнёр получит ${payout.toLocaleString('ru-RU')} ₽.`;
  }
  const currency = form.commission_currency === 'USD' ? '$' : form.commission_currency === 'EUR' ? '€' : '₽';
  return `Партнёр получит ${value.toLocaleString('ru-RU')} ${currency} за каждую подтверждённую конверсию.`;
}

export function holdHelper(days: string): string {
  if (days === '0') {
    return 'После подтверждения конверсии комиссия станет доступна к выплате сразу.';
  }
  return `После подтверждения конверсии комиссия станет доступна к выплате через ${daysLabel(Number(days))}.`;
}
