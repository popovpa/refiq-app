import { LayoutDashboard, Tag, Users, ArrowLeftRight, Wallet, Settings, Link2 } from 'lucide-react';

export type NavKey =
  | 'overview'
  | 'offers'
  | 'partners'
  | 'links'
  | 'conversions'
  | 'payouts'
  | 'settings';

export type NavItem = {
  key: NavKey;
  path: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
  labels: { ru: string; en: string };
};

export const businessNav: NavItem[] = [
  { key: 'overview', path: '/business', icon: LayoutDashboard, end: true, labels: { ru: 'Обзор', en: 'Overview' } },
  { key: 'offers', path: '/business/offers', icon: Tag, labels: { ru: 'Офферы', en: 'Offers' } },
  { key: 'partners', path: '/business/partners', icon: Users, labels: { ru: 'Партнёры', en: 'Partners' } },
  { key: 'conversions', path: '/business/conversions', icon: ArrowLeftRight, labels: { ru: 'Конверсии', en: 'Conversions' } },
  { key: 'payouts', path: '/business/payouts', icon: Wallet, labels: { ru: 'Выплаты', en: 'Payouts' } },
  { key: 'settings', path: '/business/settings', icon: Settings, labels: { ru: 'Настройки', en: 'Settings' } },
];

export const partnerNav: NavItem[] = [
  { key: 'overview', path: '/partner', icon: LayoutDashboard, end: true, labels: { ru: 'Обзор', en: 'Overview' } },
  { key: 'offers', path: '/partner/offers', icon: Tag, labels: { ru: 'Офферы', en: 'Offers' } },
  { key: 'links', path: '/partner/links', icon: Link2, labels: { ru: 'Мои ссылки', en: 'My links' } },
  { key: 'conversions', path: '/partner/conversions', icon: ArrowLeftRight, labels: { ru: 'Конверсии', en: 'Conversions' } },
  { key: 'payouts', path: '/partner/payouts', icon: Wallet, labels: { ru: 'Выплаты', en: 'Payouts' } },
  { key: 'settings', path: '/partner/settings', icon: Settings, labels: { ru: 'Настройки', en: 'Settings' } },
];
