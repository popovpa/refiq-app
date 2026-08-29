import type { LucideIcon } from 'lucide-react';
import { Info } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

const toneStyles = {
  purple: 'bg-brand-soft text-brand',
  orange: 'bg-orange-50 text-warning',
  blue: 'bg-blue-50 text-info',
  teal: 'bg-accent text-primary',
  pink: 'bg-pink-soft text-pink',
  green: 'bg-emerald-50 text-success',
} as const;

export type StatTone = keyof typeof toneStyles;

interface StatCardProps {
  title: string;
  value: string;
  icon: LucideIcon;
  tone?: StatTone;
  trend?: string;
  trendLabel?: string;
  onClick?: () => void;
  className?: string;
  compact?: boolean;
}

export function StatCard({
  title,
  value,
  icon: Icon,
  tone = 'teal',
  trend,
  trendLabel,
  onClick,
  className,
  compact = false,
}: StatCardProps) {
  const trendNegative = Boolean(trend && trend.trim().startsWith('-'));
  const content = (
    <>
      <div className={cn('flex items-start justify-between gap-2', compact ? 'mb-2' : 'mb-3')}>
        <div
          className={cn(
            'rounded-md flex items-center justify-center',
            compact ? 'w-8 h-8' : 'w-9 h-9',
            toneStyles[tone],
          )}
        >
          <Icon size={compact ? 16 : 18} strokeWidth={2} aria-hidden />
        </div>
        {!onClick && (
          <button type="button" className="text-muted-foreground/60 hover:text-muted-foreground" aria-label="info">
            <Info size={14} aria-hidden />
          </button>
        )}
      </div>
      <p className="text-xs font-medium text-muted-foreground mb-1">{title}</p>
      <p className="flex items-baseline gap-2 min-w-0">
        <span
          className={cn(
            'font-semibold tracking-tight text-foreground leading-none truncate',
            compact ? 'text-lg' : 'text-[22px]',
          )}
        >
          {value}
        </span>
        {trend && (
          <span className={cn('text-xs font-medium shrink-0', trendNegative ? 'text-destructive' : 'text-success')}>
            {trend}
          </span>
        )}
      </p>
      {trendLabel && <p className="mt-1 text-xs text-muted-foreground truncate">{trendLabel}</p>}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(
          'ui-card min-w-0 w-full text-left transition-colors hover:bg-muted/30',
          compact ? 'p-3' : 'p-4',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
          className,
        )}
      >
        {content}
      </button>
    );
  }

  return <div className={cn('ui-card min-w-0', compact ? 'p-3' : 'p-4', className)}>{content}</div>;
}
