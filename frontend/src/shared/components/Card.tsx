import { cn } from '@/shared/utils/cn';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
}

export function Card({ children, className, padding = true }: CardProps) {
  return (
    <div className={cn('ui-card', padding && 'p-5', className)}>{children}</div>
  );
}

export function CardHeader({
  title,
  action,
  className,
}: {
  title: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center justify-between gap-3 mb-4', className)}>
      <h2 className="ui-section-title">{title}</h2>
      {action}
    </div>
  );
}
