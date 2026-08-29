import { Bell, CalendarDays } from 'lucide-react';
import { RoleContextDropdown } from '@/shared/components/RoleContextDropdown';
import { MobileMenuButton } from './Sidebar';

export function Header({ onOpenMobileMenu }: { onOpenMobileMenu?: () => void }) {
  return (
    <header className="h-16 border-b border-border/80 bg-card/90 backdrop-blur sticky top-0 z-20 flex items-center justify-between gap-4 px-4 lg:px-6">
      <div className="flex items-center gap-3 min-w-0">
        <MobileMenuButton onClick={() => onOpenMobileMenu?.()} />
        <RoleContextDropdown />
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <button
          type="button"
          className="hidden md:flex items-center gap-2 h-9 px-3 rounded-md border bg-card text-sm text-muted-foreground hover:bg-muted/50"
        >
          <CalendarDays size={15} />
          <span>Последние 7 дней</span>
        </button>

        <button
          type="button"
          className="relative w-9 h-9 rounded-md border bg-card flex items-center justify-center text-muted-foreground hover:bg-muted/50"
          aria-label="Notifications"
        >
          <Bell size={16} />
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-destructive text-white text-[10px] font-semibold flex items-center justify-center">
            3
          </span>
        </button>
      </div>
    </header>
  );
}
