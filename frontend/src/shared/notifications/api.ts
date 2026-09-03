import { api } from '@/shared/api/client';
import type { AppNotification } from './types';

export const notificationKeys = {
  unread: ['notifications', 'unread-count'] as const,
  list: (limit: number) => ['notifications', 'list', limit] as const,
};

export function fetchUnreadCount() {
  return api.get<{ unread_count: number }>('/notifications/unread-count');
}

export function fetchNotifications(limit = 20) {
  return api.get<{ items: AppNotification[] }>(`/notifications?limit=${limit}`);
}

export function markNotificationRead(id: number) {
  return api.post<{ notification: AppNotification; unread_count: number }>(`/notifications/${id}/read`);
}

export function markAllNotificationsRead() {
  return api.post<{ updated: number; unread_count: number }>('/notifications/read-all');
}
