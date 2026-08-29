import { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { PanelLeftClose, PanelLeft, Menu, X } from 'lucide-react';
import { useAuth } from '@/shared/hooks/useAuth';
import { cn } from '@/shared/utils/cn';
import { businessNav, partnerNav, type NavItem } from './nav';
import { roleContextLabel } from '@/shared/layout/roleContext';
import logoMark from '@/assets/brand/logo.png';
import logoLabel from '@/assets/brand/label.png';

function Logo({ collapsed }: { collapsed?: boolean }) {
  return (
    <div
      className={cn('flex items-center min-w-0', collapsed ? 'justify-center' : 'gap-2')}
      aria-label="RefIQ"
    >
      <img
        src={logoMark}
        alt=""
        className="h-8 w-auto max-w-[40px] object-contain object-center shrink-0 select-none"
        draggable={false}
      />
      {!collapsed && (
        <img
          src={logoLabel}
          alt="RefIQ"
          className="h-[18px] w-auto max-w-[132px] object-contain object-left select-none"
          draggable={false}
        />
      )}
    </div>
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
        'flex items-center gap-3 rounded-md text-sm font-medium transition-colors',
        collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2.5',
        isActive
          ? 'bg-accent text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      <item.icon size={18} strokeWidth={2} />
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

  const openProfile = () => {
    onMobileClose?.();
    navigate('/profile');
  };

  const content = (
    <aside
      className={cn(
        'h-screen sticky top-0 flex flex-col bg-card border-r border-border/80 transition-all',
        collapsed ? 'w-[76px]' : 'w-[240px]',
      )}
    >
      <div className={cn('h-16 flex items-center px-4 border-b border-border/70', collapsed && 'justify-center px-2')}>
        <Logo collapsed={collapsed} />
        {onMobileClose && (
          <button className="ml-auto lg:hidden p-1 text-muted-foreground" onClick={onMobileClose}>
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {menu.map((item) => (
          <NavItemLink key={item.key} item={item} collapsed={collapsed} lang={lang} onNavigate={onMobileClose} />
        ))}
      </nav>

      <div className="p-3 border-t border-border/70 space-y-1">
        <button
          type="button"
          onClick={openProfile}
          className={cn(
            'w-full flex items-center gap-3 rounded-md text-left transition-colors',
            collapsed ? 'justify-center px-2 py-2' : 'px-3 py-2',
            profileActive ? 'bg-accent text-primary' : 'hover:bg-muted',
          )}
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand to-primary text-white flex items-center justify-center text-sm font-semibold shrink-0 overflow-hidden">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
            ) : (
              user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || '?'
            )}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{displayName}</p>
              <p className="text-xs text-muted-foreground truncate">{roleLabel}</p>
            </div>
          )}
        </button>
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className={cn(
            'hidden lg:flex w-full items-center gap-3 rounded-md text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors',
            collapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2.5',
          )}
        >
          {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          {!collapsed && <span>Свернуть меню</span>}
        </button>
      </div>
    </aside>
  );

  return (
    <>
      <div className="hidden lg:block">{content}</div>
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-foreground/30" onClick={onMobileClose} />
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
      className="lg:hidden p-2 rounded-md hover:bg-muted text-muted-foreground"
      aria-label="Открыть меню"
    >
      <Menu size={18} />
    </button>
  );
}
