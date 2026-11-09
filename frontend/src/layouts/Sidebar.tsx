import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { PanelLeftClose, PanelLeft, Menu, X } from 'lucide-react';
import { useAuth } from '@/shared/hooks/useAuth';
import { cn } from '@/shared/utils/cn';
import { businessNav, partnerNav, type NavItem } from './nav';
import { roleContextLabel } from '@/shared/layout/roleContext';
import sidebarLogo from '@/assets/brand/sidebar-logo.png';
import sidebarMark from '@/assets/brand/sidebar-mark.png';

function Logo({ collapsed }: { collapsed?: boolean }) {
  return (
    <img
      src={collapsed ? sidebarMark : sidebarLogo}
      alt="RefIQ"
      className={cn(
        'object-contain object-left select-none',
        collapsed ? 'h-8 w-8' : 'h-8 w-auto max-w-[168px]',
      )}
      draggable={false}
    />
  );
}

function NavItemLink({
  item,
  collapsed,
  lang,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  lang: 'ru' | 'en';
  onNavigate?: () => void;
}) {
  const location = useLocation();
  const isActive = item.end
    ? location.pathname === item.path
    : location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);

  return (
    <NavLink
      to={item.path}
      end={item.end}
      onClick={onNavigate}
      aria-label={item.labels.en}
      title={item.labels[lang]}
      className={cn(
        'flex items-center gap-2.5 rounded-lg text-[13px] min-h-[42px] transition-colors duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#A4D0FF]',
        collapsed ? 'justify-center px-2' : 'px-3',
        isActive
          ? 'bg-nav-active text-white font-semibold'
          : 'text-nav-text font-medium hover:bg-nav-hover hover:text-nav-bright',
      )}
    >
      <item.icon size={18} strokeWidth={1.75} />
      {!collapsed && <span>{item.labels[lang]}</span>}
    </NavLink>
  );
}

export function Sidebar({
  mobileOpen,
  onMobileClose,
}: {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}) {
  const { user, session } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const activeRole = session?.active_role === 'partner' ? 'partner' : session?.active_role === 'business' ? 'business' : 'business';
  const menu = activeRole === 'partner' ? partnerNav : businessNav;
  const lang: 'ru' | 'en' = user?.language === 'en' ? 'en' : 'ru';
  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || (lang === 'en' ? 'User' : 'Пользователь');
  const roleLabel = roleContextLabel(activeRole, lang);
  const profileActive = location.pathname === '/profile';
  const compact = collapsed && !mobileOpen;

  useEffect(() => {
    if (!mobileOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onMobileClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener('keydown', onKey);
    };
  }, [mobileOpen, onMobileClose]);

  const openProfile = () => {
    onMobileClose?.();
    navigate('/profile');
  };

  const content = (
    <aside
      className={cn(
        'h-screen sticky top-0 flex flex-col bg-nav text-nav-text',
        compact ? 'w-[76px]' : 'w-[242px]',
        onMobileClose && 'max-lg:w-[min(284px,calc(100vw-48px))]',
      )}
    >
      <div className={cn('h-16 flex items-center px-3', compact && 'justify-center px-2')}>
        <Logo collapsed={compact} />
        {onMobileClose && (
          <button
            type="button"
            className="ml-auto lg:hidden p-1.5 rounded-md text-nav-text hover:bg-nav-hover hover:text-nav-bright"
            onClick={onMobileClose}
            aria-label="Закрыть меню"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="flex-1 px-2.5 py-2 space-y-1 overflow-y-auto">
        {menu.map((item) => (
          <NavItemLink key={item.key} item={item} collapsed={compact} lang={lang} onNavigate={onMobileClose} />
        ))}
      </nav>

      <div className="px-2.5 py-3 border-t border-nav-divider space-y-1">
        <button
          type="button"
          onClick={openProfile}
          className={cn(
            'w-full flex items-center gap-2.5 rounded-lg text-left min-h-[42px] transition-colors duration-150',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#A4D0FF]',
            compact ? 'justify-center px-2' : 'px-2.5',
            profileActive ? 'bg-nav-active text-white' : 'hover:bg-nav-hover',
          )}
        >
          <div className="w-8 h-8 rounded-full bg-nav-avatar text-nav-ink flex items-center justify-center text-sm font-semibold shrink-0 overflow-hidden">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || '?'
            )}
          </div>
          {!compact && (
            <div className="min-w-0">
              <p className={cn('text-[13px] font-semibold truncate', profileActive ? 'text-white' : 'text-nav-bright')}>{displayName}</p>
              <p className={cn('text-[11px] truncate', profileActive ? 'text-white/80' : 'text-nav-label')}>{roleLabel}</p>
            </div>
          )}
        </button>
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className={cn(
            'hidden lg:flex w-full items-center gap-2.5 rounded-lg text-[13px] font-medium text-nav-text hover:bg-nav-hover hover:text-nav-bright transition-colors duration-150 min-h-[42px]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#A4D0FF]',
            compact ? 'justify-center px-2' : 'px-3',
          )}
        >
          {compact ? <PanelLeft size={18} strokeWidth={1.75} /> : <PanelLeftClose size={18} strokeWidth={1.75} />}
          {!compact && <span>Свернуть меню</span>}
        </button>
      </div>
    </aside>
  );

  return (
    <>
      <div className="hidden lg:block">{content}</div>
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-nav-shade/40" onClick={onMobileClose} />
          <div className="absolute inset-y-0 left-0 z-50">{content}</div>
        </div>
      )}
    </>
  );
}

export function MobileMenuButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="lg:hidden h-9 w-9 inline-flex items-center justify-center rounded-md border border-border bg-card text-foreground hover:bg-muted"
      aria-label="Открыть меню"
    >
      <Menu size={18} />
    </button>
  );
}
