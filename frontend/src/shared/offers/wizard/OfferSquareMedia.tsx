import { cn } from '@/shared/utils/cn';

export function OfferSquareMedia({
  src,
  className,
  emptyLabel = 'Нет изображения',
}: {
  src?: string | null;
  className?: string;
  emptyLabel?: string;
}) {
  return (
    <div
      className={cn(
        'aspect-square w-full overflow-hidden rounded-lg border border-border/70 bg-muted/20',
        className,
      )}
    >
      {src ? (
        <img src={src} alt="" className="block size-full object-cover object-center" />
      ) : (
        <div className="flex h-full w-full items-center justify-center px-3 text-center">
          <p className="text-sm text-muted-foreground">{emptyLabel}</p>
        </div>
      )}
    </div>
  );
}
