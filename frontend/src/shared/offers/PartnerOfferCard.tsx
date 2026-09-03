import { type KeyboardEvent } from 'react';
import { Button } from '@/shared/components/Button';
import { OfferImage } from '@/shared/offers/OfferImage';
import { conversionLabel } from '@/shared/offers/labels';
import { OWN_OFFER_PROMOTE_PENDING_LABEL } from '@/shared/offers/promoteOwnOffer';
import type { OfferListItem } from '@/shared/offers/types';
import {
  accessBadge,
  formatCommissionContext,
  formatCommissionPrimary,
  formatLinksCount,
  formatOfferCr,
  formatOfferEpc,
  formatPartnerPromotionStats,
} from '@/shared/offers/partnerOfferCardFormat';
import { cn } from '@/shared/utils/cn';

interface PartnerOfferCardProps {
  offer: OfferListItem;
  joined: boolean;
  pending: boolean;
  joinPending: boolean;
  promoteOwnPending?: boolean;
  onOpen: (offerId: OfferListItem['id']) => void;
  onGetLink: (offer: OfferListItem) => void;
  onOpenLinks: (offer: OfferListItem) => void;
  onJoinOpen: (offer: OfferListItem) => void;
  onRequestAccess: (offer: OfferListItem) => void;
  onCancelRequest: (offerId: OfferListItem['id']) => void;
  onPromoteOwn?: (offer: OfferListItem) => void;
}

export function PartnerOfferCard({
  offer,
  joined,
  pending,
  joinPending,
  promoteOwnPending = false,
  onOpen,
  onGetLink,
  onOpenLinks,
  onJoinOpen,
  onRequestAccess,
  onCancelRequest,
  onPromoteOwn,
}: PartnerOfferCardProps) {
  const rule = offer.commission_rules?.[0];
  const access = accessBadge(offer.access_policy);
  const epc = formatOfferEpc(offer);
  const cr = formatOfferCr(offer);
  const promotionStatus = offer.promotion_status || 'NOT_STARTED';
  const activeLinks = offer.active_links_count ?? 0;
  const totalLinks = offer.total_links_count ?? 0;
  const isOwn = Boolean(offer.is_own_offer);
  const offerPaused = offer.status === 'paused';
  const isPromoting = !isOwn && joined && promotionStatus === 'ACTIVE';
  const isPaused = !isOwn && joined && promotionStatus === 'PAUSED';
  const canCreateLink = !isOwn && joined && offer.status === 'active';
  const myStats = formatPartnerPromotionStats(offer);

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onOpen(offer.id);
    }
  };

  const stopCardActivation = (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
  };

  return (
    <article
      role="button"
      tabIndex={0}
      aria-label={`Открыть оффер ${offer.name}`}
      onClick={() => onOpen(offer.id)}
      onKeyDown={handleKeyDown}
      className={cn(
        'ui-card p-4 cursor-pointer',
        'transition-[border-color,box-shadow,background-color] duration-[180ms] ease-in-out',
        'hover:border-primary/25 hover:shadow-soft hover:bg-muted/20',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
      )}
    >
      <div className="flex items-start gap-3">
        <OfferImage src={offer.image_url} name={offer.name} size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <h3 className="font-semibold text-[15px] leading-snug truncate">{offer.name}</h3>
            {isOwn && (
              <span
                className="ui-badge shrink-0 bg-brand-soft text-brand"
                title="Оффер создан вашим бизнесом."
              >
                Ваш оффер
              </span>
            )}
            {isOwn && offerPaused && (
              <span className="ui-badge shrink-0 bg-yellow-50 text-yellow-700">Приостановлен</span>
            )}
          </div>
          {offer.category && (
            <p className="text-xs text-muted-foreground mt-0.5">{offer.category}</p>
          )}
        </div>
        <div className="text-right shrink-0 pl-2">
          <p className="text-lg font-semibold text-brand leading-none tracking-tight">
            {formatCommissionPrimary(rule)}
          </p>
          <p className="text-[11px] leading-snug text-muted-foreground mt-1 max-w-[108px] ml-auto">
            {formatCommissionContext(offer.conversion_type, rule)}
          </p>
        </div>
      </div>

      {offer.description && (
        <p className="text-sm text-muted-foreground line-clamp-2 mt-2 leading-snug">
          {offer.description}
        </p>
      )}

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs min-w-0">
        <span className="font-medium text-foreground">{conversionLabel(offer.conversion_type)}</span>
        <span className="text-muted-foreground" title={epc.title}>
          EPC {epc.value}
        </span>
        <span className="text-muted-foreground" title={cr.title}>
          CR {cr.value}
        </span>
        <span className="text-muted-foreground">GEO {offer.geo || '—'}</span>
      </div>

      <div className="mt-2.5 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-1.5 min-w-0">
          {!isOwn && <span className={cn('ui-badge shrink-0', access.className)}>{access.label}</span>}
          {!isOwn && pending && (
            <span className="ui-badge bg-yellow-50 text-yellow-700">Заявка рассматривается</span>
          )}
        </div>

        <div
          className="flex flex-col items-stretch sm:items-end gap-1.5 min-w-0"
          onClick={stopCardActivation}
          onKeyDown={stopCardActivation}
        >
          {isPromoting && (
            <>
              <span className="ui-badge w-fit bg-success/10 text-success inline-flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-current" aria-hidden />
                Продвигается · {formatLinksCount(activeLinks)}
              </span>
              <div className="text-right">
                <p className="text-[11px] text-muted-foreground">Моё продвижение</p>
                <p className="text-xs text-foreground mt-0.5" title={myStats.title}>
                  {myStats.value}
                </p>
              </div>
            </>
          )}
          {isPaused && (
            <span className="ui-badge w-fit bg-yellow-50 text-yellow-700">
              Продвижение приостановлено · {formatLinksCount(totalLinks)}
            </span>
          )}

          <div className="flex flex-wrap items-center justify-end gap-2 min-h-8">
            {isOwn && offer.status === 'active' && (
              <Button
                size="sm"
                disabled={promoteOwnPending}
                onClick={(event) => {
                  stopCardActivation(event);
                  onPromoteOwn?.(offer);
                }}
              >
                {promoteOwnPending ? OWN_OFFER_PROMOTE_PENDING_LABEL : 'Продвигать свой оффер'}
              </Button>
            )}
            {isOwn && offerPaused && (
              <Button size="sm" disabled title="Оффер приостановлен">
                Продвижение недоступно
              </Button>
            )}
            {!isOwn && joined && (isPromoting || isPaused) && (
              <>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={(event) => {
                    stopCardActivation(event);
                    onOpenLinks(offer);
                  }}
                >
                  Мои ссылки
                </Button>
                {canCreateLink && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(event) => {
                      stopCardActivation(event);
                      onGetLink(offer);
                    }}
                  >
                    + Новая ссылка
                  </Button>
                )}
              </>
            )}
            {!isOwn && joined && !isPromoting && !isPaused && (
              <Button
                size="sm"
                onClick={(event) => {
                  stopCardActivation(event);
                  onGetLink(offer);
                }}
              >
                Получить ссылку
              </Button>
            )}
            {!isOwn && pending && (
              <Button
                size="sm"
                variant="ghost"
                onClick={(event) => {
                  stopCardActivation(event);
                  onCancelRequest(offer.id);
                }}
              >
                Отменить заявку
              </Button>
            )}
            {!isOwn && !joined && !pending && offer.access_policy === 'open' && (
              <Button
                size="sm"
                onClick={(event) => {
                  stopCardActivation(event);
                  onJoinOpen(offer);
                }}
                disabled={joinPending}
              >
                Получить ссылку
              </Button>
            )}
            {!isOwn && !joined && !pending && offer.access_policy === 'approval' && (
              <Button
                size="sm"
                onClick={(event) => {
                  stopCardActivation(event);
                  onRequestAccess(offer);
                }}
              >
                Запросить доступ
              </Button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
