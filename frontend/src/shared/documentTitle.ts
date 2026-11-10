import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';

const BRAND = 'RefIQ';

/** Browser tab title: `Офферы - RefIQ`. Empty page name falls back to the brand. */
export function formatDocumentTitle(page?: string | null): string {
  const name = page?.replace(/\s+/g, ' ').trim();
  return name ? `${name} - ${BRAND}` : BRAND;
}

/**
 * Static section title for a pathname.
 * `null` means the screen sets its own title (offer name, wizard step, auth state).
 */
export function routeDocumentTitle(pathname: string): string | null {
  const path = pathname.replace(/\/+$/, '') || '/';

  if (path === '/' || path === '/business/billing') return null;
  if (path === '/register' || path === '/reset-password' || path === '/confirm-account') return null;
  if (path === '/business/offers/new') return null;
  if (/^\/business\/offers\/[^/]+$/.test(path)) return null;
  if (/^\/partner\/offers\/[^/]+$/.test(path)) return null;

  const exact: Record<string, string> = {
    '/login': 'Вход',
    '/forgot-password': 'Восстановление пароля',
    '/onboarding': 'Онбординг',
    '/profile': 'Профиль пользователя',
    '/notifications': 'Уведомления',
    '/business': 'Обзор',
    '/business/offers': 'Офферы',
    '/business/partners': 'Партнёры',
    '/business/conversions': 'Конверсии',
    '/business/payouts': 'Выплаты партнёрам',
    '/partner': 'Обзор',
    '/partner/offers': 'Офферы',
    '/partner/links': 'Мои ссылки',
    '/partner/conversions': 'Конверсии',
    '/partner/payouts': 'Начисления и выплаты',
    '/partner/settings': 'Настройки',
  };
  if (exact[path]) return exact[path];

  if (/^\/business\/offers\/[^/]+\/edit$/.test(path)) return 'Редактирование оффера';
  if (path === '/business/settings' || path.startsWith('/business/settings/')) return 'Настройки';
  if (path === '/business/analytics' || path.startsWith('/business/analytics/')) return 'Аналитика';
  if (path === '/partner/analytics' || path.startsWith('/partner/analytics/')) return 'Аналитика';

  return 'Страница не найдена';
}

/** Sets the browser tab title for screens whose name is not known from the URL alone. */
export function useDocumentTitle(page?: string | null) {
  useLayoutEffect(() => {
    const name = page?.trim();
    if (!name) return;
    document.title = formatDocumentTitle(name);
  }, [page]);
}

/** Keeps the browser tab in sync with the current section. */
export function DocumentTitle() {
  const { pathname } = useLocation();
  const title = routeDocumentTitle(pathname);

  useLayoutEffect(() => {
    if (!title) return;
    document.title = formatDocumentTitle(title);
  }, [title]);

  return null;
}
