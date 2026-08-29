import { type ReactNode } from 'react';
import { Copy, ExternalLink, Pencil, X } from 'lucide-react';
import { DestinationUrlBlock } from '@/shared/links/DestinationUrlBlock';
import { TrackingLinkQrBlock } from '@/shared/links/TrackingLinkQrBlock';
import { Button } from '@/shared/components/Button';
import { OfferImage } from '@/shared/offers/OfferImage';
import { trafficLabel } from '@/shared/offers/labels';
import { displayTrackingUrl, partnerQrCodeDownloadPath, partnerQrCodeUrl, publicTrackingUrl } from '@/shared/offers/trackingLink';
import {
  formatLinkCreatedAt,
  formatLinkCr,
  formatLinkEarned,
  formatLinkStatValue,
  isUnnamedLink,
  linkDisplayName,
  linkStatusClass,
  linkStatusLabel,
  type PartnerLinkItem,
} from '@/shared/partner/links/types';
import { formatNumber } from '@/shared/utils/format';
import { cn } from '@/shared/utils/cn';

export function LinkDetailDrawer({
  link,
  onClose,
  onEdit,
  onCopy,
  onRequestActivate,
  onRequestDisable,
  statusPending,
}: {
  link: PartnerLinkItem;
  onClose: () => void;
  onEdit: () => void;
  onCopy: () => void;
  onRequestActivate?: () => void;
  onRequestDisable?: () => void;
  statusPending?: boolean;
}) {
  const stats = link.stats;
  const hasData = stats?.has_stat_data ?? false;
  const isActive = link.status === 'ACTIVE';

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <aside className="relative ui-card w-full max-w-md h-full shadow-soft flex flex-col border-l">
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border/70">
          <div className="min-w-0">
            <h2 className={cn('ui-section-title truncate', isUnnamedLink(link.name) && 'text-muted-foreground')}>
              {linkDisplayName(link.name)}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-4">
          <DetailRow label="Оффер">
            <div className="flex items-center gap-2.5">
              <OfferImage src={link.offer_image_url} name={link.offer_name || 'Оффер'} size="sm" />
              <span className="font-medium">{link.offer_name || 'Оффер'}</span>
            </div>
          </DetailRow>
          <DetailRow label="Ссылка">
            <code className="text-sm bg-muted px-2 py-1 rounded-md">{displayTrackingUrl(link.short_code)}</code>
          </DetailRow>
          <DetailRow label="QR-код">
            <TrackingLinkQrBlock
              imageSrc={partnerQrCodeUrl(link.id)}
              downloadEndpoint={partnerQrCodeDownloadPath(link.id)}
              shortCode={link.short_code}
            />
          </DetailRow>
          <DestinationUrlBlock url={link.destination_url} />
          <DetailRow label="Источник">
            {link.traffic_source ? (
              trafficLabel(link.traffic_source)
            ) : (
              <span className="text-muted-foreground">Не указан</span>
            )}
          </DetailRow>
          <DetailRow label="Статус">
            <div className="space-y-1.5">
              <span className={cn('ui-badge', linkStatusClass(link.status))}>{linkStatusLabel(link.status)}</span>
              <p className="text-xs font-normal text-muted-foreground">
                {isActive
                  ? 'Ссылка принимает новый трафик.'
                  : 'Новый трафик по этой ссылке не принимается. Исторические данные и конверсии сохраняются.'}
              </p>
            </div>
          </DetailRow>
          <DetailRow label="Клики">
            {formatLinkStatValue(stats?.clicks, hasData, (v) => formatNumber(v))}
          </DetailRow>
          <DetailRow label="Конверсии">
            {formatLinkStatValue(stats?.conversions, hasData, (v) => formatNumber(v))}
          </DetailRow>
          <DetailRow label="CR">{formatLinkCr(stats)}</DetailRow>
          <DetailRow label="Заработано">{formatLinkEarned(stats)}</DetailRow>
          <DetailRow label="Создана">{formatLinkCreatedAt(link.created_at)}</DetailRow>
          {link.notes?.trim() && (
            <DetailRow label="Заметка">
              <span className="text-muted-foreground whitespace-pre-wrap">{link.notes}</span>
            </DetailRow>
          )}
        </div>

        <div className="p-5 border-t border-border/70 flex flex-wrap gap-2">
          <Button size="sm" onClick={onCopy}>
            <Copy size={14} /> Copy
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => window.open(publicTrackingUrl(link.short_code), '_blank', 'noopener,noreferrer')}
          >
            <ExternalLink size={14} /> Open
          </Button>
          <Button size="sm" variant="secondary" onClick={onEdit}>
            <Pencil size={14} /> Редактировать
          </Button>
          {isActive
            ? onRequestDisable && (
                <Button size="sm" variant="secondary" disabled={statusPending} onClick={onRequestDisable}>
                  {statusPending ? 'Сохранение...' : 'Отключить ссылку'}
                </Button>
              )
            : onRequestActivate && (
                <Button size="sm" disabled={statusPending} onClick={onRequestActivate}>
                  {statusPending ? 'Сохранение...' : 'Активировать ссылку'}
                </Button>
              )}
        </div>
      </aside>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 text-sm items-start">
      <span className="text-muted-foreground">{label}</span>
      <div className="font-medium min-w-0">{children}</div>
    </div>
  );
}
