import { useState } from 'react';
import { Menu } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui';
import { GlobalSearch } from '@/components/GlobalSearch';

const ROLE_LABELS: Record<string, string> = {
  super: 'Супер',
  support: 'Поддержка',
  finance: 'Финансы',
};

export function Header({ onOpenMenu }: { onOpenMenu?: () => void }) {
  const { session, logout } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <header className="h-16 shrink-0 border-b bg-card px-4 flex items-center gap-4">
      <button
        type="button"
        className="lg:hidden h-9 w-9 inline-flex items-center justify-center rounded-md border border-border bg-card text-foreground hover:bg-muted"
        onClick={onOpenMenu}
        aria-label="Открыть меню"
      >
        <Menu size={18} />
      </button>
      <GlobalSearch />
      <div className="relative">
        <button type="button" className="text-sm font-medium" onClick={() => setOpen((v) => !v)}>
          {session?.email}
        </button>
        {open && (
          <div className="absolute right-0 mt-2 w-56 ui-card shadow-soft p-2 z-30">
            <div className="px-2 py-1 text-xs text-muted-foreground">
              {ROLE_LABELS[session?.role || ''] || session?.role}
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start"
              onClick={() => {
                setOpen(false);
                logout();
              }}
            >
              Выйти
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
