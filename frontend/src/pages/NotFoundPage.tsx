import { Link } from 'react-router-dom';
import logoMark from '@/assets/brand/logo.png';
import logoLabel from '@/assets/brand/label.png';

export function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
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
            className="inline-flex items-center justify-center w-full h-11 px-5 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary-hover transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/15"
          >
            На главную
          </Link>
        </div>
      </div>
    </div>
  );
}
