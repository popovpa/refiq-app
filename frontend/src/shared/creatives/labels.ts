import type { BannerFormat, CreativeType } from './types';

export const CREATIVE_TYPES: { value: CreativeType; label: string; hint: string }[] = [
  { value: 'text', label: 'Рекламный текст', hint: 'Заголовок, текст и призыв к действию' },
  { value: 'social_post', label: 'Telegram / Social post', hint: 'Пост с CTA и хештегами' },
  { value: 'banner', label: 'Баннер', hint: 'Изображение в готовом формате' },
];

export const CHANNELS = [
  { value: 'telegram', label: 'Telegram' },
  { value: 'social', label: 'Social' },
  { value: 'vk', label: 'VK' },
  { value: 'instagram', label: 'Instagram' },
];

export const GOALS = [
  { value: 'sale', label: 'Продажа' },
  { value: 'lead', label: 'Заявка' },
  { value: 'signup', label: 'Регистрация' },
];

export const STYLES = [
  { value: 'neutral', label: 'Нейтральный' },
  { value: 'expert', label: 'Экспертный' },
  { value: 'promotional', label: 'Продающий' },
];

export const BANNER_FORMATS: { value: BannerFormat; label: string; hint: string }[] = [
  { value: 'square_1_1', label: '1:1', hint: '1080×1080' },
  { value: 'portrait_4_5', label: '4:5', hint: '1080×1350' },
  { value: 'landscape_16_9', label: '16:9', hint: '1200×675' },
  { value: 'story_9_16', label: '9:16', hint: '1080×1920' },
];

export const CHANNEL_LABELS: Record<string, string> = {
  general: 'Общий',
  telegram: 'Telegram',
  social: 'Social',
  vk: 'VK Реклама',
  instagram: 'Instagram',
  yandex_direct: 'Яндекс Директ',
  meta_ads: 'Meta Ads (Facebook)',
  google_ads: 'Google Ads',
  tiktok_ads: 'TikTok Ads',
  email: 'Email',
  other: 'Другое',
};

export const TEXT_CHANNEL_LABELS: Record<string, string> = {
  general: 'Универсальный',
  telegram: 'Telegram',
  social: 'Social',
  vk: 'VK Реклама',
  instagram: 'Instagram',
  yandex_direct: 'Яндекс Директ',
  meta_ads: 'Meta Ads (Facebook)',
  google_ads: 'Google Ads',
  tiktok_ads: 'TikTok Ads',
  email: 'Email',
  other: 'Другое',
};

export const FORMAT_LABELS: Record<string, string> = {
  square_1_1: '1:1',
  portrait_4_5: '4:5',
  landscape_16_9: '16:9',
  story_9_16: '9:16',
};

export const TYPE_LABELS: Record<string, string> = {
  text: 'Рекламный текст',
  social_post: 'Telegram / Social post',
  banner: 'Баннер',
};

export const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  draft: { label: 'Черновик', className: 'bg-muted text-muted-foreground' },
  active: { label: 'Опубликован', className: 'bg-accent text-primary' },
  archived: { label: 'Архив', className: 'bg-muted text-muted-foreground' },
  generating: { label: 'Генерируется', className: 'bg-accent text-primary' },
  queued: { label: 'В очереди', className: 'bg-muted text-muted-foreground' },
  failed: { label: 'Ошибка', className: 'bg-destructive/10 text-destructive' },
  cancelled: { label: 'Остановлено', className: 'bg-muted text-muted-foreground' },
};

export const VARIANT_KIND_LABELS: Record<string, string> = {
  short: 'Короткий',
  expert: 'Экспертный',
  promotional: 'Продающий',
};

export function formatCreativeText(item: {
  headline?: string | null;
  body?: string | null;
  cta?: string | null;
  hashtags?: string[];
  items?: string[];
  descriptions?: string[];
}): string {
  if (item.descriptions && item.descriptions.length) {
    const headlines = (item.items && item.items.length ? item.items : [item.headline]).filter(Boolean);
    return [`Заголовки:\n${headlines.join('\n')}`, `Описания:\n${item.descriptions.join('\n')}`]
      .filter(Boolean)
      .join('\n\n');
  }
  if (item.items && item.items.length > 1) {
    const lines = item.items.filter(Boolean).join('\n');
    const tags = (item.hashtags || []).map((tag) => `#${tag}`).join(' ');
    return [lines, item.cta, tags].filter(Boolean).join('\n\n');
  }
  return formatSingleVariant(item);
}

export function formatSingleVariant(item: {
  headline?: string | null;
  body?: string | null;
  cta?: string | null;
  hashtags?: string[];
}): string {
  const parts = [item.headline, item.body, item.cta].filter(Boolean);
  const tags = (item.hashtags || []).map((tag) => `#${tag}`).join(' ');
  return [parts.join('\n\n'), tags].filter(Boolean).join('\n\n');
}

export function ruCount(n: number, one: string, few: string, many: string) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} ${one}`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} ${few}`;
  return `${n} ${many}`;
}
