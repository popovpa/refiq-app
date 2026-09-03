import { addCalendarDays, calendarDateFromInstant, getBrowserTimeZone } from '@/shared/dateRange/timezone';

export type NotificationTimeGroup = 'today' | 'yesterday' | 'older';

export function notificationTimeParts(iso: string | null, now: Date = new Date(), timeZone = getBrowserTimeZone()) {
  if (!iso) return { group: 'older' as NotificationTimeGroup, label: '' };
  const created = new Date(iso);
  if (Number.isNaN(created.getTime())) return { group: 'older' as NotificationTimeGroup, label: '' };

  const today = calendarDateFromInstant(now, timeZone);
  const day = calendarDateFromInstant(created, timeZone);
  const yesterday = addCalendarDays(today.year, today.month, today.day, -1);

  const sameDay = (a: { year: number; month: number; day: number }, b: typeof a) =>
    a.year === b.year && a.month === b.month && a.day === b.day;

  if (sameDay(day, today)) {
    const diffMs = Math.max(0, now.getTime() - created.getTime());
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return { group: 'today' as const, label: 'сейчас' };
    if (minutes < 60) return { group: 'today' as const, label: `${minutes} мин` };
    const hours = Math.floor(minutes / 60);
    return { group: 'today' as const, label: `${hours} ч` };
  }

  if (sameDay(day, yesterday)) {
    const time = created.toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone,
    });
    return { group: 'yesterday' as const, label: time };
  }

  return {
    group: 'older' as const,
    label: created.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', timeZone }),
  };
}

export function groupLabel(group: NotificationTimeGroup): string {
  if (group === 'today') return 'Сегодня';
  if (group === 'yesterday') return 'Вчера';
  return 'Ранее';
}
