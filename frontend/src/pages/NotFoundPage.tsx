import { Link } from 'react-router-dom';
import { useEffect } from 'react';
import logoMark from '@/assets/brand/logo.png';
import logoLabel from '@/assets/brand/label.png';

export function NotFoundPage() {
  useEffect(() => {
    document.title = 'Страница не найдена — RefIQ';
    return () => {
      document.title = 'RefIQ';
    };
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,hsla(174,72%,40%,0.10),transparent_42%),radial-gradient(circle_at_bottom_left,hsla(248,78%,62%,0.10),transparent_42%)]" />
      <div className="relative w-full max-w-md">
        <div className="text-center mb-7">
          <div className="inline-flex items-center justify-center gap-2.5 mb-3">
            <img
              src={logoMark}
              alt=""
              className="h-9 w-auto max-w-[40px] object-contain object-center select-none"
              draggable={false}
            />
            <img
              src={logoLabel}
              alt="RefIQ"
              className="h-5 w-auto max-w-[140px] object-contain object-left select-none"
              draggable={false}
            />
          </div>
          <p className="text-muted-foreground text-sm">Платформа партнёрских продаж</p>
        </div>
        <div className="ui-card p-8 shadow-soft text-center">
          <p className="text-xs font-semibold uppercase tracking-wider text-primary mb-2">Ошибка 404</p>
          <h1 className="text-2xl font-semibold tracking-tight mb-3">Такой страницы нет</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Адрес не существует или страница была перемещена. Вернитесь на главную, чтобы продолжить работу в
            RefIQ.
          </p>
          <Link
            to="/"
            className="inline-flex items-center justify-center w-full h-11 px-5 rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            На главную
          </Link>
        </div>
      </div>
    </div>
  );
}
