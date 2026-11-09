import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, X } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { OfferImage } from '@/shared/offers/OfferImage';
import { CreateTrackingLinkModal } from '@/shared/offers/CreateTrackingLinkModal';
import {
  formatCommissionContext,
  formatCommissionPrimary,
} from '@/shared/offers/partnerOfferCardFormat';
import type { CommissionRule } from '@/shared/offers/types';
import { cn } from '@/shared/utils/cn';

export type LinkOfferOption = {
  id: number | string;
  name: string;
  image_url?: string | null;
  category?: string | null;
  conversion_type?: string;
  commission_rules?: CommissionRule[];
  status?: string;
  partner_status?: string | null;
};

function isEligibleOffer(offer: LinkOfferOption): boolean {
  return offer.partner_status === 'approved' && offer.status === 'active';
}

function offerSelectorMeta(offer: LinkOfferOption): string {
  const rule = offer.commission_rules?.[0] as CommissionRule | undefined;
  const commission = `${formatCommissionPrimary(rule)} ${formatCommissionContext(offer.conversion_type, rule)}`.trim();
  return offer.category ? `${commission} · ${offer.category}` : commission;
}

export function GetLinkModal({
  lockedOffer,
  lockedDestinationId,
  onClose,
}: {
  lockedOffer?: LinkOfferOption | null;
  lockedDestinationId?: number | null;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [pickedId, setPickedId] = useState(lockedOffer ? String(lockedOffer.id) : '');
  const [selectorOpen, setSelectorOpen] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery<{ items: LinkOfferOption[] }>({
    queryKey: ['partner', 'offers', 'my'],
    queryFn: () => api.get('/partner/offers'),
    enabled: !lockedOffer,
  });

  const eligibleOffers = useMemo(
    () => (data?.items || []).filter(isEligibleOffer),
    [data],
  );
  const selected = lockedOffer || eligibleOffers.find((offer) => String(offer.id) === pickedId) || null;

  if (selected) {
    return (
      <CreateTrackingLinkModal
        mode="partner"
        offerId={selected.id}
        initialDestinationId={lockedDestinationId}
        onClose={onClose}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-[440px] rounded-2xl p-6 shadow-soft space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-semibold tracking-tight">Получить ссылку</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>
        {isLoading ? (
          <Skeleton className="h-24 rounded-lg" />
        ) : isError ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Не удалось загрузить офферы.</p>
            <Button variant="secondary" onClick={() => refetch()}>Повторить</Button>
          </div>
        ) : !eligibleOffers.length ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Нет офферов, доступных для продвижения.</p>
            <Button
              onClick={() => {
                onClose();
                navigate('/partner/offers');
              }}
            >
              Открыть офферы
            </Button>
          </div>
        ) : (
          <div className="relative">
            <span className="mb-2 block text-[15px] font-semibold">Оффер</span>
            <button
              type="button"
              className="ui-input flex h-12 items-center justify-between gap-2 text-left"
              onClick={() => setSelectorOpen((open) => !open)}
            >
              <span className="text-muted-foreground">Выберите оффер</span>
              <ChevronDown size={16} className="text-muted-foreground shrink-0" />
            </button>
            {selectorOpen && (
              <div className="absolute z-10 mt-1 w-full ui-card p-1 max-h-56 overflow-auto">
                {eligibleOffers.map((offer) => (
                  <button
                    key={offer.id}
                    type="button"
                    className={cn('w-full rounded-md px-2 py-2 text-left hover:bg-muted/60')}
                    onClick={() => {
                      setPickedId(String(offer.id));
                      setSelectorOpen(false);
                    }}
                  >
                    <span className="flex items-center gap-3 min-w-0">
                      <OfferImage src={offer.image_url} name={offer.name} size="sm" />
                      <span className="min-w-0">
                        <span className="block text-sm font-medium truncate">{offer.name}</span>
                        <span className="block text-xs text-muted-foreground truncate">{offerSelectorMeta(offer)}</span>
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
