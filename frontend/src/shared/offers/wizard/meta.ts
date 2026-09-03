import type { OfferFormValues } from '@/shared/offers/types';

export const WIZARD_STEPS = [
  { id: 'product', label: 'Продукт' },
  { id: 'reward', label: 'Вознаграждение' },
  { id: 'promotion', label: 'Условия продвижения' },
  { id: 'review', label: 'Проверка и публикация' },
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
  {
    value: 'signup',
    title: 'Регистрация',
    description: 'Партнёр получает вознаграждение за подтверждённую регистрацию.',
  },
  {
    value: 'application',
    title: 'Одобренная заявка',
    description: 'Партнёр получает вознаграждение после одобрения заявки.',
  },
] as const;

export const ACCESS_CARDS = [
  {
    value: 'open',
    title: 'Все партнёры',
    description: 'Оффер доступен всем подходящим партнёрам.',
  },
  {
    value: 'approval',
    title: 'Только одобренные',
    description: 'Партнёр должен получить одобрение бизнеса.',
  },
  {
    value: 'invite_only',
    title: 'По приглашению',
    description: 'Оффер доступен только приглашённым партнёрам.',
  },
] as const;

export const ATTRIBUTION_PRESETS = [7, 14, 30, 60, 90] as const;

export const TRAFFIC_SOURCE_CARDS = [
  { keys: ['content', 'seo'], label: 'Сайты и блоги' },
  { keys: ['telegram'], label: 'Telegram' },
  { keys: ['social'], label: 'Социальные сети' },
  { keys: ['email'], label: 'Email' },
  { keys: ['ppc'], label: 'Контекстная реклама' },
  { keys: ['youtube'], label: 'Видео' },
] as const;

export const RESTRICTION_PRESETS = [
  { id: 'brand_bidding', label: 'Brand bidding запрещён', traffic: ['ppc'] as const },
  { id: 'spam', label: 'Spam запрещён', note: 'Запрещён spam-трафик.' },
  { id: 'motivated', label: 'Мотивированный трафик запрещён', note: 'Запрещён мотивированный трафик.' },
  { id: 'cashback', label: 'Cashback запрещён', note: 'Запрещён cashback-трафик.' },
  { id: 'coupon', label: 'Coupon traffic запрещён', note: 'Запрещён coupon-трафик.' },
  { id: 'misleading', label: 'Misleading advertising запрещён', note: 'Запрещена вводящая в заблуждение реклама.' },
] as const;

export function buildPartnerNotes(form: OfferFormValues): string | null {
  const parts: string[] = [];
  if (form.restrictions_custom.trim()) parts.push(form.restrictions_custom.trim());
  if (form.partner_notes.trim()) parts.push(form.partner_notes.trim());
  return parts.length ? parts.join('\n\n') : null;
}

export function commissionExample(form: OfferFormValues): string | null {
  const value = Number(form.commission_value);
  if (!(value > 0)) return null;
  if (form.commission_type === 'percent') {
    const sample = 20000;
    const payout = Math.round((sample * value) / 100);
    return `При продаже на 20 000 ₽ партнёр получит ${payout.toLocaleString('ru-RU')} ₽.`;
  }
  const currency = form.commission_currency === 'USD' ? '$' : form.commission_currency === 'EUR' ? '€' : '₽';
  return `Партнёр получит ${value.toLocaleString('ru-RU')} ${currency} за каждую подтверждённую конверсию.`;
}
