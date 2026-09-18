/** Russian labels aligned with the main RefIQ cabinet terminology. */

export const STATUS_LABELS: Record<string, string> = {
  active: 'Активен',
  inactive: 'Неактивен',
  disabled: 'Отключен',
  paused: 'Приостановлен',
  draft: 'Черновик',
  archived: 'Архивный',
  closing: 'Закрывается',
  suspended: 'Приостановлен',
  blocked: 'Заблокирован',
  approved: 'Одобрена',
  rejected: 'Отклонена',
  pending: 'Ожидает',
  processing: 'В обработке',
  paid: 'Выплачено',
  cancelled: 'Отменена',
  accepted: 'Принят',
  duplicate: 'Дубликат',
  connected: 'Подключен',
  not_connected: 'Не подключен',
  no_activity: 'Нет активности',
  not_configured: 'Не настроено',
  awaiting_first_request: 'Ожидает первый запрос',
  healthy: 'В норме',
  degraded: 'Деградация',
  ok: 'OK',
  success: 'Успешно',
  error: 'Ошибка',
  failed: 'Ошибка',
  attributed: 'Атрибутирована',
  calculated: 'Рассчитана',
  waiting_approval: 'Ожидает одобрения',
  pending_verification: 'На проверке',
  verified: 'Подтверждено',
  review_required: 'Требуется проверка',
  unknown: 'Неизвестно',
};

/** Link statuses use feminine forms like the partner cabinet. */
export function statusLabel(status?: string | null): string {
  if (status == null || status === '') return '—';
  const raw = String(status);
  if (raw === 'ACTIVE') return 'Активна';
  if (raw === 'DISABLED') return 'Отключена';
  if (raw === 'PENDING_VERIFICATION') return 'На проверке';
  if (raw === 'VERIFIED') return 'Подтверждено';
  if (raw === 'REVIEW_REQUIRED') return 'Требуется проверка';
  if (raw === 'REJECTED') return 'Отклонено';
  if (raw === 'BLOCKED') return 'Заблокировано';
  if (raw === 'DRAFT') return 'Черновик';
  const key = raw.toLowerCase();
  return STATUS_LABELS[key] || raw;
}

export const TAB_LABELS: Record<string, string> = {
  overview: 'Обзор',
  sites: 'Сайты',
  offers: 'Офферы',
  partners: 'Партнёры',
  conversions: 'Конверсии',
  finance: 'Финансы',
  profile: 'Профиль',
  links: 'Ссылки',
  clicks: 'Клики',
  commissions: 'Комиссии',
  payouts: 'Выплаты',
};

export const COLUMN_LABELS: Record<string, string> = {
  domain: 'Домен',
  status: 'Статус',
  name: 'Название',
};

export const AGGREGATE_LABELS: Record<string, string> = {
  sites: 'Сайты',
  offers: 'Офферы',
  partners: 'Партнёры',
  tracking_links: 'Ссылки',
  clicks_30d: 'Клики за 30 дней',
  conversions_30d: 'Конверсии за 30 дней',
  commissions_30d: 'Комиссии за 30 дней',
};

export function aggregateLabel(key: string): string {
  return AGGREGATE_LABELS[key] || key.replace(/_/g, ' ');
}

export const ENTITY_TYPE_LABELS: Record<string, string> = {
  business: 'Бизнес',
  partner: 'Партнёр',
  offer: 'Оффер',
  site: 'Сайт',
  tracking_link: 'Ссылка',
  click: 'Клик',
  conversion: 'Конверсия',
  commission: 'Комиссия',
  payout: 'Выплата',
  legal_entity: 'Юридические данные',
  postback: 'Postback',
  campaign: 'Кампания',
};

export function entityTypeLabel(type?: string | null): string {
  if (!type) return '';
  return ENTITY_TYPE_LABELS[type] || type;
}
