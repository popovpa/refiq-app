import { RoleContextDropdown } from '@/shared/components/RoleContextDropdown';
import { NotificationBell } from '@/shared/notifications/NotificationBell';
import { MobileMenuButton } from './Sidebar';

export function Header({ onOpenMobileMenu }: { onOpenMobileMenu?: () => void }) {
  return (
    <header className="h-16 shrink-0 border-b border-border bg-card sticky top-0 z-20 flex items-center justify-between gap-4 px-4 lg:px-8">
      <div className="flex items-center gap-3 min-w-0">
        <MobileMenuButton onClick={() => onOpenMobileMenu?.()} />
        <RoleContextDropdown />
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <NotificationBell />
      </div>
    </header>
  );
}
