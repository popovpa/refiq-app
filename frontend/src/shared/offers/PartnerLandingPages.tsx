import { ExternalLink } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import {
  destinationTypeLabel,
  shortDestinationUrl,
  type OfferDestinationItem,
} from '@/shared/offers/destinations';

export function PartnerLandingPages({
  items,
  canCreate,
  onCreate,
}: {
  items: OfferDestinationItem[];
  canCreate: boolean;
  onCreate: (destinationId: number) => void;
}) {
  if (!items.length) return null;
  return (
    <section className="ui-card p-4 shrink-0">
      <h2 className="ui-section-title mb-2.5">Посадочные страницы</h2>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-border/70 px-3 py-2">
            <div className="flex items-center gap-3 min-w-0">
              {item.image_url && (
                <img src={item.image_url} alt="" className="h-10 w-10 rounded-md object-cover shrink-0" />
              )}
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">
                  {item.title}
                  {item.is_primary && <span className="text-muted-foreground font-normal"> · Основная</span>}
                </p>
                <p className="text-xs text-muted-foreground truncate mt-0.5">
                  {destinationTypeLabel(item.type)} · {shortDestinationUrl(item.url)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <a href={item.url} target="_blank" rel="noreferrer">
                <Button size="sm" variant="secondary">
                  <ExternalLink size={14} />
                  Открыть страницу
                </Button>
              </a>
              {canCreate && (
                <Button size="sm" onClick={() => onCreate(item.id)}>
                  Создать ссылку
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
