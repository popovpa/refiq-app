import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bell } from 'lucide-react';
import { fetchUnreadCount, notificationKeys } from './api';
import { NotificationPopover } from './NotificationPopover';

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { data } = useQuery({
    queryKey: notificationKeys.unread,
    queryFn: fetchUnreadCount,
    refetchOnWindowFocus: true,
    staleTime: 30_000,
  });
  const unread = data?.unread_count ?? 0;
  const badge = unread > 99 ? '99+' : String(unread);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        className="relative w-9 h-9 rounded-md border bg-card flex items-center justify-center text-muted-foreground hover:bg-muted/50"
        aria-label="Уведомления"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((current) => !current)}
      >
        <Bell size={16} />
        {unread > 0 ? (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-destructive text-white text-[10px] font-semibold flex items-center justify-center">
            {badge}
          </span>
        ) : null}
      </button>
      {open ? <NotificationPopover onClose={() => setOpen(false)} /> : null}
    </div>
  );
}
