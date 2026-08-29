import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, CheckCircle2, ChevronDown, Users } from 'lucide-react';
import { useAuth } from '@/shared/hooks/useAuth';
import { useRoleContext } from '@/shared/hooks/useContext';
import { useToast } from '@/shared/components/Toast';
import {
  activeRoleContexts,
  hasMultipleRoleContexts,
  roleContextLabel,
  ROLE_CONTEXT_LABELS,
  type RoleContext,
} from '@/shared/layout/roleContext';
import { cn } from '@/shared/utils/cn';

const WORKSPACES: Record<
  RoleContext,
  {
    Icon: typeof Building2;
    iconWrap: string;
    badge: string;
    description: { ru: string; en: string };
  }
> = {
  business: {
    Icon: Building2,
    iconWrap: 'bg-accent text-primary',
    badge: 'bg-accent text-primary',
    description: {
      ru: 'Управление офферами и партнёрами',
      en: 'Manage offers and partners',
    },
  },
  partner: {
    Icon: Users,
    iconWrap: 'bg-brand-soft text-brand',
    badge: 'bg-brand-soft text-brand',
    description: {
      ru: 'Продвижение офферов и заработок',
      en: 'Promote offers and earn',
    },
  },
};

export function RoleContextDropdown({ className }: { className?: string }) {
  const { user, session } = useAuth();
  const { switchRole } = useRoleContext();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const lang: 'ru' | 'en' = user?.language === 'en' ? 'en' : 'ru';
  const activeRole = (session?.active_role || 'business') as RoleContext;
  const availableRoles = activeRoleContexts(user?.roles);
  const showDropdown = hasMultipleRoleContexts(user?.roles);
  const activeMeta = WORKSPACES[activeRole] || WORKSPACES.business;
  const ActiveIcon = activeMeta.Icon;

  const workspaceName = (role: RoleContext) => {
    const name = role === 'business' ? session?.business_name : session?.partner_name;
    return name?.trim() || roleContextLabel(role, lang);
  };

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  if (!showDropdown) {
    return null;
  }

  const handleSwitch = (role: RoleContext) => {
    if (role === activeRole) {
      setOpen(false);
      return;
    }

    switchRole.mutate(role, {
      onSuccess: () => {
        addToast(
          lang === 'en'
            ? `Workspace: ${ROLE_CONTEXT_LABELS[role].en}`
            : `Рабочее пространство: ${ROLE_CONTEXT_LABELS[role].ru}`,
          'success',
        );
        setOpen(false);
        navigate(`/${role}`);
      },
      onError: () => {
        addToast(
          lang === 'en' ? 'Could not switch workspace' : 'Не удалось переключить пространство',
          'error',
        );
      },
    });
  };

  return (
    <div ref={containerRef} className={cn('relative min-w-0', className)}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={lang === 'en' ? 'Switch workspace' : 'Переключить рабочее пространство'}
        disabled={switchRole.isPending}
        onClick={() => setOpen((current) => !current)}
        className={cn(
          'inline-flex items-center gap-2 h-9 max-w-full px-2.5 sm:px-3 rounded-md border bg-card text-sm font-medium',
          'text-foreground hover:bg-muted/50 transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
          open && 'bg-muted/50',
        )}
      >
        <ActiveIcon size={16} className={cn('shrink-0', activeRole === 'partner' ? 'text-brand' : 'text-primary')} aria-hidden />
        <span className="truncate max-w-[108px] sm:max-w-[180px]">{workspaceName(activeRole)}</span>
        <span className={cn('ui-badge shrink-0', activeMeta.badge)}>
          {roleContextLabel(activeRole, lang)}
        </span>
        <ChevronDown
          size={15}
          className={cn('text-muted-foreground shrink-0 transition-transform', open && 'rotate-180')}
          aria-hidden
        />
      </button>

      {open && (
        <div
          role="listbox"
          aria-label={lang === 'en' ? 'Switch workspace' : 'Переключить рабочее пространство'}
          className="absolute left-0 top-full z-30 mt-1 w-[min(calc(100vw-2rem),360px)] ui-card p-2 shadow-soft"
        >
          <p className="px-2 pt-1 pb-2 text-xs text-muted-foreground">
            {lang === 'en' ? 'Switch workspace' : 'Переключить рабочее пространство'}
          </p>
          <div className="space-y-1">
            {availableRoles.map((role) => {
              const meta = WORKSPACES[role];
              const Icon = meta.Icon;
              const selected = role === activeRole;
              const name = workspaceName(role);
              const roleLabel = roleContextLabel(role, lang);

              return (
                <button
                  key={role}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  aria-current={selected ? 'true' : undefined}
                  disabled={switchRole.isPending}
                  onClick={() => handleSwitch(role)}
                  className={cn(
                    'w-full flex items-start gap-3 rounded-lg px-2.5 py-2.5 text-left transition-colors',
                    'hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
                    selected && 'bg-accent border border-primary/35 hover:bg-accent',
                    !selected && 'border border-transparent',
                  )}
                >
                  <span className={cn('w-9 h-9 rounded-md flex items-center justify-center shrink-0', meta.iconWrap)}>
                    <Icon size={16} aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold truncate">
                      {name} — {roleLabel}
                    </span>
                    <span className="block text-xs text-muted-foreground mt-0.5 leading-snug">
                      {meta.description[lang]}
                    </span>
                  </span>
                  {selected && (
                    <span className="shrink-0 flex flex-col items-end gap-2 pt-0.5">
                      <CheckCircle2 size={18} className="text-primary" aria-hidden />
                      <span className="ui-badge bg-accent text-primary">
                        {lang === 'en' ? 'Current' : 'Текущее'}
                      </span>
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
