import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api } from '@/shared/api/client';
import { DestinationUrlBlock } from '@/shared/links/DestinationUrlBlock';
import { TrackingLinkQrBlock } from '@/shared/links/TrackingLinkQrBlock';
import { trafficLabel } from '@/shared/offers/labels';
import { businessQrCodeDownloadPath, businessQrCodeUrl, displayTrackingUrl } from '@/shared/offers/trackingLink';
import { linkStatusClass, linkStatusLabel } from '@/shared/partner/links/types';
import { cn } from '@/shared/utils/cn';
import { partnerDisplayName } from '@/shared/partners/displayName';

export type BusinessPromotionLink = {
  id: number | string;
  name?: string | null;
  url: string;
  short_code?: string;
  destination_url?: string | null;
  partner_name?: string | null;
  traffic_source?: string | null;
  status: string;
  clicks: number;
  conversions: number;
};

type HistoryResponse = {
  items: Array<{
    created_at?: string | null;
    destination_url?: string | null;
    actor_name?: string | null;
  }>;
};

export function BusinessLinkDetailDrawer({
  offerId,
  link,
  variant = 'partner',
  onClose,
  onEditDestination,
}: {
  offerId: string;
  link: BusinessPromotionLink;
  variant?: 'partner' | 'own';
  onClose: () => void;
  onEditDestination: () => void;
}) {
  const isOwn = variant === 'own';
  const [historyOpen, setHistoryOpen] = useState(false);
  const shortCode = link.short_code || link.url.split('/').pop() || '';
  const { data: history, isLoading: historyLoading } = useQuery<HistoryResponse>({
    queryKey: ['business', 'offers', offerId, 'links', link.id, 'destination-history'],
    queryFn: () => api.get(`/business/offers/${offerId}/links/${link.id}/destination-history`),
    enabled: historyOpen,
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <aside className="relative ui-card w-full max-w-md h-full shadow-soft flex flex-col border-l">
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border/70">
          <div className="min-w-0">
            <h2 className="ui-section-title truncate">
              {isOwn ? link.name || 'Собственная ссылка' : partnerDisplayName(link.partner_name) || link.name || 'Ссылка'}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-4">
          {!isOwn && <DetailRow label="Партнёр">{partnerDisplayName(link.partner_name) || '—'}</DetailRow>}
          <DetailRow label="Ссылка">
            <code className="text-sm bg-muted px-2 py-1 rounded-md">{displayTrackingUrl(shortCode)}</code>
          </DetailRow>
          <DetailRow label="QR-код">
            <TrackingLinkQrBlock
              imageSrc={businessQrCodeUrl(offerId, link.id)}
              downloadEndpoint={businessQrCodeDownloadPath(offerId, link.id)}
              shortCode={shortCode}
            />
          </DetailRow>
          {!isOwn && (
            <DetailRow label="Источник">
              {link.traffic_source ? trafficLabel(link.traffic_source) : '—'}
            </DetailRow>
          )}
          <DetailRow label="Клики">{link.clicks ?? 0}</DetailRow>
          <DetailRow label="Конверсии">{link.conversions ?? 0}</DetailRow>
          <DetailRow label="Статус">
            <span className={cn('ui-badge', linkStatusClass(link.status))}>{linkStatusLabel(link.status)}</span>
          </DetailRow>
          <DestinationUrlBlock url={link.destination_url} onEdit={onEditDestination} />

          <div>
            <button
              type="button"
              className="text-sm text-primary hover:underline"
              onClick={() => setHistoryOpen((open) => !open)}
            >
              История изменений →
            </button>
            {historyOpen && (
              <div className="mt-3 space-y-3">
                {historyLoading && <p className="text-sm text-muted-foreground">Загрузка...</p>}
                {!historyLoading && (history?.items.length ?? 0) === 0 && (
                  <p className="text-sm text-muted-foreground">Изменений пока нет.</p>
                )}
                {history?.items.map((item, index) => (
                  <div key={`${item.created_at}-${index}`} className="text-sm space-y-0.5">
                    <p className="text-muted-foreground">{formatHistoryDate(item.created_at)}</p>
                    <p className="font-medium break-all">{item.destination_url}</p>
                    {item.actor_name && <p className="text-xs text-muted-foreground">{item.actor_name}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 text-sm items-start">
      <span className="text-muted-foreground">{label}</span>
      <div className="font-medium min-w-0">{children}</div>
    </div>
  );
}

function formatHistoryDate(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
