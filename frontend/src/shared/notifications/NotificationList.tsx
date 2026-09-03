import { Link } from 'react-router-dom';
import { cn } from '@/shared/utils/cn';
import { notificationDestination, notificationTitle } from './registry';
import { groupLabel, notificationTimeParts, type NotificationTimeGroup } from './time';
import type { AppNotification } from './types';

const GROUP_ORDER: NotificationTimeGroup[] = ['today', 'yesterday', 'older'];

export function NotificationList({
  items,
  onOpen,
}: {
  items: AppNotification[];
  onOpen: (item: AppNotification) => void;
}) {
  const grouped = GROUP_ORDER.map((group) => ({
    group,
    items: items.filter((item) => notificationTimeParts(item.created_at).group === group),
  })).filter((entry) => entry.items.length > 0);

  return (
    <div className="max-h-[min(24rem,70vh)] overflow-auto">
      {grouped.map((entry) => (
        <section key={entry.group} className="px-1 pb-2">
          <h3 className="px-2 pt-2 pb-1 text-xs font-medium text-muted-foreground">{groupLabel(entry.group)}</h3>
          <ul>
            {entry.items.map((item) => {
              const time = notificationTimeParts(item.created_at);
              const destination = notificationDestination(item);
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onOpen(item)}
                    className={cn(
                      'w-full text-left rounded-md px-2 py-2 hover:bg-muted/60 transition-colors',
                      !item.is_read && 'bg-accent/40',
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <span
                        className={cn(
                          'mt-1.5 w-1.5 h-1.5 rounded-full shrink-0',
                          item.is_read ? 'bg-transparent' : 'bg-primary',
                        )}
                        aria-hidden
                      />
                      <div className="min-w-0 flex-1">
                        <p className={cn('text-sm truncate', !item.is_read && 'font-medium')}>
                          {notificationTitle(item)}
                        </p>
                        {item.message ? (
                          <p className="text-xs text-muted-foreground truncate mt-0.5">{item.message}</p>
                        ) : null}
                        <p className="text-[11px] text-muted-foreground mt-0.5">{time.label}</p>
                        {destination ? <span className="sr-only">Открыть связанный объект</span> : null}
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function NotificationFooterLink({ onClick }: { onClick: () => void }) {
  return (
    <div className="border-t border-border/70 px-3 py-2">
      <Link
        to="/notifications"
        onClick={onClick}
        className="text-xs font-medium text-primary hover:underline"
      >
        Все уведомления →
      </Link>
    </div>
  );
}
