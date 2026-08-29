import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { entityHref } from '@/lib/navigation';

export function EntityLink({
  type,
  id,
  children,
}: {
  type: string;
  id?: string | number | null;
  children?: ReactNode;
}) {
  const href = entityHref(type, id);
  if (!href) return <span className="text-muted-foreground">{children ?? '—'}</span>;
  return (
    <Link to={href} className="text-primary hover:underline">
      {children ?? id}
    </Link>
  );
}
