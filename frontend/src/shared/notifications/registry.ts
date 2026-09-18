import type { AppNotification, NotificationSeverity } from './types';

export type NotificationTypeConfig = {
  fallbackTitle: string;
  fallbackSeverity: NotificationSeverity;
  destination?: (notification: AppNotification) => string | null;
};

export const DEFAULT_NOTIFICATION_CONFIG: NotificationTypeConfig = {
  fallbackTitle: 'Уведомление',
  fallbackSeverity: 'INFO',
};

export const notificationTypeRegistry: Record<string, NotificationTypeConfig> = {
  SDK_CONNECTED: {
    fallbackTitle: 'SDK успешно подключён',
    fallbackSeverity: 'SUCCESS',
    destination: (item) =>
      item.destination ||
      (item.metadata.site_id ? `/business/settings?tab=sites&site=${item.metadata.site_id}` : '/business/settings?tab=sites'),
  },
  SDK_EVENTS_STOPPED: {
    fallbackTitle: 'SDK перестал передавать события',
    fallbackSeverity: 'WARNING',
    destination: (item) =>
      item.destination ||
      (item.metadata.site_id ? `/business/settings?tab=sites&site=${item.metadata.site_id}` : '/business/settings?tab=sites'),
  },
  POSTBACK_FAILED: {
    fallbackTitle: 'Postback не проходит',
    fallbackSeverity: 'CRITICAL',
    destination: (item) => item.destination || '/business/settings?tab=integrations&integration=postback',
  },
  POSTBACK_HIGH_ERROR_RATE: {
    fallbackTitle: 'Высокий процент ошибочных postback',
    fallbackSeverity: 'WARNING',
    destination: (item) => item.destination || '/business/settings?tab=integrations&integration=postback',
  },
  SITE_DOMAIN_VERIFIED: {
    fallbackTitle: 'Домен сайта подтверждён',
    fallbackSeverity: 'SUCCESS',
    destination: (item) =>
      item.destination ||
      (item.metadata.site_id ? `/business/settings?tab=sites&site=${item.metadata.site_id}` : '/business/settings?tab=sites'),
  },
  SITE_VERIFICATION_FAILED: {
    fallbackTitle: 'Проверка сайта не пройдена',
    fallbackSeverity: 'CRITICAL',
    destination: (item) =>
      item.destination ||
      (item.metadata.site_id ? `/business/settings?tab=sites&site=${item.metadata.site_id}` : '/business/settings?tab=sites'),
  },
  PAYOUT_DUE: {
    fallbackTitle: 'Подтвердите выплату партнёру',
    fallbackSeverity: 'WARNING',
    destination: (item) => item.destination || '/business/payouts',
  },
  PAYOUT_REMINDER: {
    fallbackTitle: 'Напоминание о выплате партнёру',
    fallbackSeverity: 'WARNING',
    destination: (item) => item.destination || '/business/payouts',
  },
  PAYOUT_OVERDUE: {
    fallbackTitle: 'Просрочена выплата партнёру',
    fallbackSeverity: 'CRITICAL',
    destination: (item) => item.destination || '/business/payouts',
  },
  PARTNER_TRAFFIC_SUSPENDED: {
    fallbackTitle: 'Партнёрский трафик приостановлен',
    fallbackSeverity: 'CRITICAL',
    destination: (item) => item.destination || '/business/payouts',
  },
};

export function notificationConfig(type: string): NotificationTypeConfig {
  return notificationTypeRegistry[type] || DEFAULT_NOTIFICATION_CONFIG;
}

export function notificationDestination(item: AppNotification): string | null {
  if (item.destination) return item.destination;
  return notificationConfig(item.type).destination?.(item) ?? null;
}

export function notificationTitle(item: AppNotification): string {
  return item.title || notificationConfig(item.type).fallbackTitle;
}
