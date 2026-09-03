import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Skeleton } from '@/shared/components/Skeleton';
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  notificationKeys,
} from './api';
import { NotificationFooterLink, NotificationList } from './NotificationList';
import { notificationDestination } from './registry';
import type { AppNotification } from './types';

export function NotificationPopover({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: notificationKeys.list(20),
    queryFn: () => fetchNotifications(20),
  });

  const markOne = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: (payload) => {
      queryClient.setQueryData(notificationKeys.unread, { unread_count: payload.unread_count });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'list'] });
    },
  });

  const markAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      queryClient.setQueryData(notificationKeys.unread, { unread_count: 0 });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'list'] });
    },
  });

  const openItem = (item: AppNotification) => {
    markOne.mutate(item.id);
    const destination = notificationDestination(item);
    onClose();
    if (destination) navigate(destination);
  };

  return (
    <div className="absolute right-0 top-full z-30 mt-1 w-[min(calc(100vw-2rem),380px)] ui-card shadow-soft overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-3 py-2.5 border-b border-border/70">
        <h2 className="text-sm font-semibold">Уведомления</h2>
        <button
          type="button"
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending}
          className="text-xs font-medium text-primary hover:underline disabled:opacity-50"
        >
          Прочитать все
        </button>
      </div>

      {isLoading ? (
        <div className="p-3 space-y-2">
          {[1, 2, 3].map((key) => (
            <Skeleton key={key} className="h-12 rounded-md" />
          ))}
        </div>
      ) : isError ? (
        <div className="p-4 text-center space-y-2">
          <p className="text-sm text-muted-foreground">Не удалось загрузить уведомления</p>
          <button type="button" onClick={() => refetch()} className="text-xs font-medium text-primary hover:underline">
            Повторить
          </button>
        </div>
      ) : !data?.items.length ? (
        <p className="p-6 text-sm text-center text-muted-foreground">Нет новых уведомлений</p>
      ) : (
        <NotificationList items={data.items} onOpen={openItem} />
      )}

      <NotificationFooterLink onClick={onClose} />
    </div>
  );
}
