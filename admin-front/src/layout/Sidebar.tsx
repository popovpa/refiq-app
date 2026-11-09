import { useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Building2,
  Handshake,
  Globe,
  Megaphone,
  Link2,
  MousePointerClick,
  BadgeCheck,
  ArrowLeftRight,
  Wallet,
  Banknote,
  ScrollText,
  Scale,
  LayoutDashboard,
  X,
} from 'lucide-react';
import { cn } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { ADMIN_FINANCE } from '@/lib/permissions';
import sidebarLogo from '@/assets/brand/sidebar-logo.png';

const NAV: {
  heading: string | null;
  finance?: boolean;
  items: { to: string; label: string; icon: typeof LayoutDashboard; end?: boolean }[];
}[] = [
  { heading: null, items: [{ to: '/', label: 'Обзор', icon: LayoutDashboard, end: true }] },
  {
    heading: 'Аккаунты',
    items: [
      { to: '/businesses', label: 'Бизнесы', icon: Building2 },
      { to: '/partners', label: 'Партнёры', icon: Handshake },
    ],
  },
  {
    heading: 'Продвижение',
    items: [
      { to: '/sites', label: 'Сайты', icon: Globe },
      { to: '/offers', label: 'Офферы', icon: Megaphone },
      { to: '/tracking-links', label: 'Ссылки', icon: Link2 },
    ],
  },
  {
    heading: 'Трафик',
    items: [
      { to: '/clicks', label: 'Клики', icon: MousePointerClick },
      { to: '/conversions', label: 'Конверсии', icon: BadgeCheck },
      { to: '/postbacks', label: 'Postback', icon: ArrowLeftRight },
    ],
  },
  {
    heading: 'Финансы',
    finance: true,
    items: [
      { to: '/commissions', label: 'Комиссии', icon: Wallet },
      { to: '/payouts', label: 'Выплаты', icon: Banknote },
      { to: '/legal-entities', label: 'Юридические данные', icon: Scale },
    ],
  },
  {
    heading: 'Администрирование',
    items: [{ to: '/audit', label: 'Аудит', icon: ScrollText }],
  },
];

export function Sidebar({ onClose }: { onClose?: () => void }) {
  const { has } = useAuth();

  useEffect(() => {
    if (!onClose) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  return (
    <aside
      className={cn(
        'w-[242px] shrink-0 bg-nav text-nav-text flex flex-col h-full',
        onClose && 'w-[min(284px,calc(100vw-48px))]',
      )}
    >
      <div className="h-16 px-3 flex items-center gap-2">
        <img
          src={sidebarLogo}
          alt="RefIQ"
          className="h-8 w-auto max-w-[150px] object-contain object-left select-none"
          draggable={false}
        />
        {!onClose && (
          <span className="text-[10px] uppercase tracking-wider text-nav-label">Admin</span>
        )}
        {onClose && (
          <button
            type="button"
            className="ml-auto p-1.5 rounded-md text-nav-text hover:bg-nav-hover hover:text-nav-bright"
            onClick={onClose}
            aria-label="Закрыть меню"
          >
            <X size={18} />
          </button>
        )}
      </div>
      <nav className="flex-1 overflow-auto py-2 px-2.5">
        {NAV.map((section) => {
          if (section.finance && !has(ADMIN_FINANCE)) return null;
          return (
            <div key={section.heading || 'overview'} className="mb-3">
              {section.heading && (
                <div className="px-3 mb-1 mt-2 text-[10px] font-semibold uppercase tracking-wider text-nav-label">
                  {section.heading}
                </div>
              )}
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onClose}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2.5 rounded-lg px-3 min-h-[42px] text-[13px] transition-colors duration-150',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#A4D0FF]',
                      isActive
                        ? 'bg-nav-active text-white font-semibold'
                        : 'text-nav-text font-medium hover:bg-nav-hover hover:text-nav-bright',
                    )
                  }
                >
                  <item.icon size={17} strokeWidth={1.75} />
                  {item.label}
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
