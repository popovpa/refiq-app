import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="ui-card p-8 text-center">
      <h1 className="text-lg font-semibold mb-2">Страница не найдена</h1>
      <p className="text-sm text-muted-foreground mb-4">Такого маршрута в админке нет.</p>
      <Link to="/" className="text-primary text-sm">
        К обзору
      </Link>
    </div>
  );
}
