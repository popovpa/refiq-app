import type { ReactNode } from 'react';
import { cn } from '@/components/ui';
import { EmptyState, Skeleton } from '@/components/ui';
import { errorMessage, isApiError } from '@/lib/api';

export function QueryState({
  loading,
  error,
  empty,
  emptyTitle = 'Ничего не найдено',
  emptyDescription = 'Нет записей по текущим фильтрам.',
  children,
}: {
  loading: boolean;
  error: unknown;
  empty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }
  if (error) {
    const status = isApiError(error) ? error.status : 500;
    const title =
      status === 403
        ? 'Недостаточно прав'
        : status === 404
          ? 'Сущность не найдена'
          : status === 409
            ? 'Конфликт доменных правил'
            : 'Ошибка запроса';
    return <EmptyState title={title} description={errorMessage(error)} />;
  }
  if (empty) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  return <>{children}</>;
}

export function DataTable({
  columns,
  rows,
  rowKey,
  onRowClick,
}: {
  columns: { key: string; header: string; className?: string; align?: 'left' | 'right' }[];
  rows: Array<Record<string, ReactNode>>;
  rowKey?: (row: Record<string, ReactNode>, index: number) => string;
  onRowClick?: (row: Record<string, ReactNode>, index: number) => void;
}) {
  return (
    <div className="ui-card overflow-auto">
      <table className="ui-table admin-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={cn(col.className, col.align === 'right' && 'text-right')}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={rowKey ? rowKey(row, index) : String(index)}
              className={onRowClick ? 'cursor-pointer hover:bg-muted/50' : undefined}
              onClick={onRowClick ? () => onRowClick(row, index) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={cn(col.className, col.align === 'right' && 'text-right tabular-nums')}>
                  {row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OffsetPager({
  page,
  pages,
  onPage,
}: {
  page: number;
  pages: number;
  onPage: (page: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-end gap-2 mt-3 text-sm">
      <button type="button" className="ui-input !w-auto h-8" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Назад
      </button>
      <span className="text-muted-foreground">
        {page} / {pages || 1}
      </span>
      <button type="button" className="ui-input !w-auto h-8" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Вперёд
      </button>
    </div>
  );
}

export function CursorPager({
  hasMore,
  onMore,
  disabled,
}: {
  hasMore: boolean;
  onMore: () => void;
  disabled?: boolean;
}) {
  if (!hasMore) return null;
  return (
    <div className="flex justify-end mt-3">
      <button type="button" className="ui-input !w-auto h-8" disabled={disabled} onClick={onMore}>
        Показать ещё
      </button>
    </div>
  );
}
