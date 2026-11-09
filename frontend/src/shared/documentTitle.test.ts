import { describe, expect, it } from 'vitest';
import { formatDocumentTitle, routeDocumentTitle } from '@/shared/documentTitle';

describe('formatDocumentTitle', () => {
  it('joins the page name and the brand', () => {
    expect(formatDocumentTitle('Офферы')).toBe('Офферы - RefIQ');
    expect(formatDocumentTitle('Смартфон')).toBe('Смартфон - RefIQ');
    expect(formatDocumentTitle('Конверсии')).toBe('Конверсии - RefIQ');
  });

  it('falls back to the brand when the page name is empty', () => {
    expect(formatDocumentTitle('')).toBe('RefIQ');
    expect(formatDocumentTitle('   ')).toBe('RefIQ');
    expect(formatDocumentTitle(null)).toBe('RefIQ');
    expect(formatDocumentTitle(undefined)).toBe('RefIQ');
  });

  it('collapses whitespace in the page name', () => {
    expect(formatDocumentTitle('  Смартфон   X  ')).toBe('Смартфон X - RefIQ');
  });
});

describe('routeDocumentTitle', () => {
  it('names every static product section', () => {
    expect(routeDocumentTitle('/business')).toBe('Обзор');
    expect(routeDocumentTitle('/business/offers')).toBe('Офферы');
    expect(routeDocumentTitle('/business/partners')).toBe('Партнёры');
    expect(routeDocumentTitle('/business/conversions')).toBe('Конверсии');
    expect(routeDocumentTitle('/business/payouts')).toBe('Выплаты партнёрам');
    expect(routeDocumentTitle('/business/settings')).toBe('Настройки');
    expect(routeDocumentTitle('/business/settings/billing')).toBe('Настройки');
    expect(routeDocumentTitle('/business/settings/')).toBe('Настройки');
    expect(routeDocumentTitle('/partner')).toBe('Обзор');
    expect(routeDocumentTitle('/partner/offers')).toBe('Офферы');
    expect(routeDocumentTitle('/partner/links')).toBe('Мои ссылки');
    expect(routeDocumentTitle('/partner/conversions')).toBe('Конверсии');
    expect(routeDocumentTitle('/partner/payouts')).toBe('Начисления и выплаты');
    expect(routeDocumentTitle('/partner/settings')).toBe('Настройки');
    expect(routeDocumentTitle('/profile')).toBe('Профиль пользователя');
    expect(routeDocumentTitle('/notifications')).toBe('Уведомления');
    expect(routeDocumentTitle('/login')).toBe('Вход');
    expect(routeDocumentTitle('/forgot-password')).toBe('Восстановление пароля');
    expect(routeDocumentTitle('/onboarding')).toBe('Онбординг');
    expect(routeDocumentTitle('/business/offers/42/edit')).toBe('Редактирование оффера');
  });

  it('leaves dynamic screens to the page', () => {
    expect(routeDocumentTitle('/business/offers/new')).toBeNull();
    expect(routeDocumentTitle('/business/offers/42')).toBeNull();
    expect(routeDocumentTitle('/partner/offers/smartphone')).toBeNull();
    expect(routeDocumentTitle('/register')).toBeNull();
    expect(routeDocumentTitle('/reset-password')).toBeNull();
    expect(routeDocumentTitle('/confirm-account')).toBeNull();
    expect(routeDocumentTitle('/')).toBeNull();
    expect(routeDocumentTitle('/business/billing')).toBeNull();
  });

  it('names unknown addresses as not found', () => {
    expect(routeDocumentTitle('/missing')).toBe('Страница не найдена');
    expect(routeDocumentTitle('/business/offers/42/extra')).toBe('Страница не найдена');
  });
});
