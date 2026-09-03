export const NOTIFICATION_TYPES = [
  'SDK_CONNECTED',
  'SDK_EVENTS_STOPPED',
  'POSTBACK_FAILED',
  'POSTBACK_HIGH_ERROR_RATE',
  'SITE_DOMAIN_VERIFIED',
  'SITE_VERIFICATION_FAILED',
] as const;

export type NotificationType = (typeof NOTIFICATION_TYPES)[number];

export const NOTIFICATION_SEVERITIES = ['INFO', 'SUCCESS', 'WARNING', 'CRITICAL'] as const;
export type NotificationSeverity = (typeof NOTIFICATION_SEVERITIES)[number];

export type AppNotification = {
  id: number;
  type: string;
  severity: NotificationSeverity | string;
  title: string;
  message: string | null;
  is_read: boolean;
  created_at: string | null;
  read_at: string | null;
  destination: string | null;
  metadata: Record<string, unknown>;
  role_context?: string | null;
  business_id?: number | null;
  partner_id?: number | null;
};
