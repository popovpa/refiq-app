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
} from 'lucide-react';
import { cn } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { ADMIN_FINANCE } from '@/lib/permissions';
import logoMark from '@/assets/brand/logo.png';
import logoLabel from '@/assets/brand/label.png';

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

export function Sidebar() {
  const { has } = useAuth();
  return (
    <aside className="w-[240px] shrink-0 border-r bg-card flex flex-col">
      <div className="h-16 px-4 flex items-center gap-2 border-b">
        <img src={logoMark} alt="" className="h-7 w-auto select-none" draggable={false} />
        <img src={logoLabel} alt="RefIQ" className="h-4 w-auto select-none" draggable={false} />
        <span className="ml-1 text-[10px] uppercase tracking-wider text-muted-foreground">Admin</span>
      </div>
      <nav className="flex-1 overflow-auto py-3 px-2">
        {NAV.map((section) => {
          if (section.finance && !has(ADMIN_FINANCE)) return null;
          return (
            <div key={section.heading || 'overview'} className="mb-3">
              {section.heading && (
                <div className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {section.heading}
                </div>
              )}
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium',
                      isActive ? 'bg-accent text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    )
                  }
                >
                  <item.icon size={16} />
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
