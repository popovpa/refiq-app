import type { ReactNode } from 'react';
import { cn } from '@/shared/utils/cn';
import { DateRangeSelector } from './DateRangeSelector';
import type { DateRangeFilterMode, DateRangePreset } from './types';

export function PageHeading({
  title,
  dateRangeFilter,
  defaultPreset,
  extra,
  className,
}: {
  title: ReactNode;
  dateRangeFilter: DateRangeFilterMode;
  defaultPreset?: DateRangePreset;
  extra?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center justify-between gap-3 min-w-0', className)}>
      <h1 className="ui-page-title min-w-0 truncate">{title}</h1>
      <div className="flex items-center gap-2 shrink-0">
        {extra}
        {dateRangeFilter === 'header' ? <DateRangeSelector defaultPreset={defaultPreset} /> : null}
      </div>
    </div>
  );
}
