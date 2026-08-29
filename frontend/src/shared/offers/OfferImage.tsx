import { cn } from '@/shared/utils/cn';

export function OfferImage({
  src,
  name,
  size = 'sm',
}: {
  src?: string | null;
  name: string;
  size?: 'sm' | 'md' | 'detail' | 'lg';
}) {
  const box = {
    sm: 'w-9 h-9 min-w-9 min-h-9 max-w-9 max-h-9 text-xs rounded-md',
    md: 'w-14 h-14 min-w-14 min-h-14 max-w-14 max-h-14 text-sm rounded-lg',
    detail: 'w-[68px] h-[68px] min-w-[68px] min-h-[68px] max-w-[68px] max-h-[68px] text-base rounded-lg',
    lg: 'w-20 h-20 min-w-20 min-h-20 max-w-20 max-h-20 text-lg rounded-xl',
  }[size];
  const initial = name.trim().slice(0, 1).toUpperCase() || '?';

  return (
    <div
      className={cn(
        'overflow-hidden border border-border/70 flex items-center justify-center font-semibold shrink-0 aspect-square',
        box,
        src
          ? 'bg-muted text-muted-foreground'
          : 'bg-gradient-to-br from-accent via-muted to-secondary text-primary',
      )}
    >
      {src ? <img src={src} alt="" className="block size-full object-cover object-center" /> : initial}
    </div>
  );
}
