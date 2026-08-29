import { ExternalLink } from 'lucide-react';
import { Button } from '@/shared/components/Button';

export function DestinationUrlBlock({
  url,
  onEdit,
}: {
  url?: string | null;
  onEdit?: () => void;
}) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 text-sm items-start">
      <span className="text-muted-foreground">Целевая страница</span>
      <div className="min-w-0 space-y-2">
        {url ? (
          <p className="font-medium break-all">{url}</p>
        ) : (
          <p className="text-muted-foreground">Не указана</p>
        )}
        <div className="flex flex-wrap gap-2">
          {url && (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => window.open(url, '_blank', 'noopener,noreferrer')}
            >
              <ExternalLink size={14} />
              Открыть
            </Button>
          )}
          {onEdit && (
            <Button type="button" size="sm" variant="secondary" onClick={onEdit}>
              Изменить
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
