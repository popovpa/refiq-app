import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, FileText, Layers, Link2, X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import {
  selectedDestinationId,
  trackingLinkName,
  type DestinationListResponse,
  type OfferDestinationItem,
} from '@/shared/offers/destinations';
import { displayTrackingUrl, publicTrackingUrl } from '@/shared/offers/trackingLink';

type Mode = 'business' | 'partner';

interface CampaignOption {
  id: number;
  name: string;
  status?: string;
}

interface CreatedLink {
  short_code: string;
  name?: string | null;
  url?: string;
}

function errorMessage(error: unknown): string {
  const apiError = error as ApiError | undefined;
  const message = apiError?.error?.message;
  if (typeof message === 'string' && message.trim()) return message;
  return 'Не удалось создать ссылку. Попробуйте ещё раз.';
}

function activePages(items: OfferDestinationItem[] | undefined): OfferDestinationItem[] {
  return (items || []).filter((item) => item.status === 'active' && item.available !== false);
}

export function CreateTrackingLinkModal({
  mode,
  offerId,
  initialDestinationId,
  onClose,
}: {
  mode: Mode;
  offerId: string | number;
  initialDestinationId?: number | null;
  onClose: () => void;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const submitting = useRef(false);
  const [destinationId, setDestinationId] = useState(initialDestinationId ? String(initialDestinationId) : '');
  const [campaignId, setCampaignId] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const destinationsQuery = useQuery<DestinationListResponse>({
    queryKey: [mode, 'offers', offerId, 'destinations', 'link-form'],
    queryFn: () =>
      api.get(
        mode === 'business'
          ? `/business/offers/${offerId}/destinations?status=active&per_page=100`
          : `/partner/offers/${offerId}/destinations?per_page=100`,
      ),
  });
  const campaignsQuery = useQuery<{ items: CampaignOption[] }>({
    queryKey: [mode, 'offers', offerId, 'campaigns', 'link-form'],
    queryFn: () =>
      api.get(
        mode === 'business'
          ? `/business/offers/${offerId}/campaigns`
          : `/partner/campaigns?offer_id=${offerId}&status=ACTIVE`,
      ),
  });
  const namesQuery = useQuery<{ items: Array<{ name?: string | null }> }>({
    queryKey: [mode, 'offers', offerId, 'link-names'],
    queryFn: () => api.get(`/business/offers/${offerId}/links`),
    enabled: mode === 'business',
  });

  const destinations = useMemo(() => activePages(destinationsQuery.data?.items), [destinationsQuery.data]);
  const campaigns = useMemo(
    () => (campaignsQuery.data?.items || []).filter((item) => !item.status || item.status === 'ACTIVE'),
    [campaignsQuery.data],
  );
  const selected = destinations.find((item) => String(item.id) === destinationId) || null;
  const partnerMustChoose =
    mode === 'partner' && destinations.length > 1 && !destinations.some((item) => item.is_primary) && !initialDestinationId;

  useEffect(() => {
    if (!destinations.length) {
      setDestinationId('');
      return;
    }
    setDestinationId((current) =>
      selectedDestinationId(destinations, {
        preferredId: initialDestinationId,
        currentId: current,
        fallbackToFirst: mode === 'business',
      }),
    );
  }, [destinations, initialDestinationId, mode]);

  const createLink = useMutation({
    mutationFn: (body: { name: string; offerDestinationId: number; campaignId: number | null }) => {
      if (mode === 'business') {
        return api.post<CreatedLink>(`/business/offers/${offerId}/links`, {
          offer_destination_id: body.offerDestinationId,
          campaign_id: body.campaignId,
          name: body.name,
        });
      }
      return api.post<CreatedLink>('/partner/links', {
        offer_id: Number(offerId),
        offer_destination_id: body.offerDestinationId,
        name: body.name,
        ...(body.campaignId ? { campaign_id: body.campaignId } : { without_campaign: true }),
      });
    },
    onSuccess: async (link) => {
      const url = link.short_code ? publicTrackingUrl(link.short_code) : link.url || '';
      queryClient.invalidateQueries({ queryKey: ['partner', 'links'] });
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      queryClient.invalidateQueries({ queryKey: ['business', 'offers', String(offerId)] });
      const visible = link.short_code ? displayTrackingUrl(link.short_code) : url;
      try {
        if (url) await navigator.clipboard.writeText(url);
        addToast(visible ? `Ссылка создана: ${visible}` : 'Ссылка создана', 'success');
      } catch {
        addToast(visible ? `Ссылка создана: ${visible}` : 'Ссылка создана', 'success');
      }
      onClose();
    },
    onError: (error) => {
      setFormError(errorMessage(error));
    },
  });

  const submit = () => {
    if (submitting.current || createLink.isPending) return;
    if (!selected) {
      setFormError('Нет активных страниц для продвижения.');
      return;
    }
    const campaign = campaigns.find((item) => String(item.id) === campaignId) || null;
    const taken = mode === 'business' ? (namesQuery.data?.items || []).map((item) => item.name || '') : [];
    const name = trackingLinkName(selected.title, campaign?.name, taken);
    setFormError(null);
    submitting.current = true;
    createLink.mutate(
      {
        name,
        offerDestinationId: selected.id,
        campaignId: campaign ? campaign.id : null,
      },
      { onSettled: () => { submitting.current = false; } },
    );
  };

  const loading = destinationsQuery.isPending || campaignsQuery.isPending;
  const empty = !loading && destinations.length === 0;
  const canSubmit = Boolean(selected) && !createLink.isPending && !loading;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={createLink.isPending ? undefined : onClose} />
      <div className="relative ui-card w-full max-w-[440px] rounded-2xl p-6 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Link2 size={18} />
            </div>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">
              {mode === 'partner' ? 'Получить ссылку' : 'Создать ссылку'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={createLink.isPending}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Закрыть"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-6 space-y-5">
          {loading ? (
            <p className="text-sm text-muted-foreground">Загрузка страниц…</p>
          ) : empty ? (
            <p className="text-sm text-muted-foreground">
              Нет активных страниц для продвижения. Создать ссылку нельзя.
            </p>
          ) : (
            <>
              <label className="block">
                <span className="mb-2 block text-[15px] font-semibold text-foreground">
                  Страница для продвижения{mode === 'partner' ? ' *' : ''}
                </span>
                <span className="relative block">
                  <FileText size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <select
                    className="ui-input h-12 appearance-none rounded-lg pl-10 pr-10"
                    value={destinationId}
                    onChange={(event) => {
                      setDestinationId(event.target.value);
                      if (formError) setFormError(null);
                    }}
                  >
                    {partnerMustChoose && <option value="">Выберите страницу</option>}
                    {destinations.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.title}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                </span>
              </label>

              <label className="block">
                <span className="mb-2 block text-[15px] font-semibold text-foreground">Кампания</span>
                <span className="relative block">
                  <Layers size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <select
                    className="ui-input h-12 appearance-none rounded-lg pl-10 pr-10"
                    value={campaignId}
                    onChange={(event) => setCampaignId(event.target.value)}
                  >
                    <option value="">Без кампании</option>
                    {campaigns.map((campaign) => (
                      <option key={campaign.id} value={campaign.id}>
                        {campaign.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                </span>
              </label>
            </>
          )}

          {destinationsQuery.isError && (
            <p className="text-sm text-destructive">Не удалось загрузить страницы оффера.</p>
          )}
          {formError && <p className="text-sm text-destructive">{formError}</p>}

          <div className="flex justify-end gap-3 pt-1">
            <Button type="button" variant="secondary" className="min-w-[108px] rounded-lg" disabled={createLink.isPending} onClick={onClose}>
              Отмена
            </Button>
            <Button type="button" className="min-w-[148px] rounded-lg" disabled={!canSubmit} onClick={submit}>
              Создать ссылку
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
