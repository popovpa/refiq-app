import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  notificationKeys,
} from '@/shared/notifications/api';
import { NotificationList } from '@/shared/notifications/NotificationList';
import { notificationDestination } from '@/shared/notifications/registry';
import type { AppNotification } from '@/shared/notifications/types';

export function NotificationsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: notificationKeys.list(100),
    queryFn: () => fetchNotifications(100),
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
    if (destination) navigate(destination);
  };

  return (
    <div className="space-y-5 max-w-[720px]">
      <div className="flex items-center justify-between gap-3">
        <h1 className="ui-page-title">Уведомления</h1>
        <button
          type="button"
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending}
          className="text-sm font-medium text-primary hover:underline disabled:opacity-50"
        >
          Прочитать все
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((key) => (
            <Skeleton key={key} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState
          title="Не удалось загрузить уведомления"
          description="Попробуйте обновить список."
          action={{ label: 'Повторить', onClick: () => refetch() }}
        />
      ) : !data?.items.length ? (
        <EmptyState title="Нет новых уведомлений" description="Важные системные события появятся здесь." />
      ) : (
        <div className="ui-card p-2">
          <NotificationList items={data.items} onOpen={openItem} />
        </div>
      )}
    </div>
  );
}
