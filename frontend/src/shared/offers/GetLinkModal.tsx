import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, ChevronDown, Info, X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { OfferImage } from '@/shared/offers/OfferImage';
import { normalizeTrafficSource } from '@/shared/catalog/trafficSources';
import { TRAFFIC_TYPES, trafficLabel } from '@/shared/offers/labels';
import {
  formatCommissionContext,
  formatCommissionPrimary,
} from '@/shared/offers/partnerOfferCardFormat';
import { publicTrackingUrl } from '@/shared/offers/trackingLink';
import type { CommissionRule } from '@/shared/offers/types';
import { cn } from '@/shared/utils/cn';

export type LinkOfferOption = {
  id: number | string;
  name: string;
  image_url?: string | null;
  category?: string | null;
  conversion_type?: string;
  commission_rules?: CommissionRule[];
  allowed_traffic?: string[];
  forbidden_traffic?: string[];
  status?: string;
  partner_status?: string | null;
};

interface CreatedLink {
  url: string;
  short_code: string;
  name: string | null;
  traffic_source: string | null;
  offer_name?: string;
}

interface OffersResponse {
  items: LinkOfferOption[];
}

function isEligibleOffer(offer: LinkOfferOption): boolean {
  return offer.partner_status === 'approved' && offer.status === 'active';
}

function trafficOptionsForOffer(offer?: LinkOfferOption | null) {
  if (!offer) return [];
  const allowed = new Set(
    (offer.allowed_traffic || []).map((item) => normalizeTrafficSource(item) || item),
  );
  return TRAFFIC_TYPES.filter((item) => allowed.has(item.value));
}

function offerCommissionLine(offer: LinkOfferOption): string {
  const rule = offer.commission_rules?.[0] as CommissionRule | undefined;
  return `${formatCommissionPrimary(rule)} ${formatCommissionContext(offer.conversion_type, rule)}`.trim();
}

function offerSelectorMeta(offer: LinkOfferOption): string {
  const commission = offerCommissionLine(offer);
  return offer.category ? `${commission} · ${offer.category}` : commission;
}

function createLinkErrorMessage(error: unknown): string {
  const apiError = error as ApiError | undefined;
  const code = apiError?.error?.code;
  const message = apiError?.error?.message;

  if (
    code === 'OFFER_UNAVAILABLE' ||
    code === 'OFFER_APPROVAL_REQUIRED' ||
    code === 'TRAFFIC_SOURCE_FORBIDDEN' ||
    code === 'TRAFFIC_SOURCE_NOT_ALLOWED'
  ) {
    return message || 'Не удалось создать ссылку. Попробуйте ещё раз.';
  }
  if (code === 'OFFER_LANDING_MISSING' && typeof message === 'string') {
    return message;
  }
  if (apiError?.status === 403) {
    if (typeof message === 'string' && /access|одобрен/i.test(message)) {
      return 'Для этого оффера требуется одобрение.';
    }
    return 'Оффер больше недоступен для продвижения.';
  }
  return 'Не удалось создать ссылку. Попробуйте ещё раз.';
}

function OfferContextRow({ offer }: { offer: LinkOfferOption }) {
  return (
    <div className="flex items-center gap-3 min-w-0">
      <OfferImage src={offer.image_url} name={offer.name} size="sm" />
      <div className="min-w-0">
        <p className="text-sm font-medium truncate">{offer.name}</p>
        <p className="text-xs text-muted-foreground truncate mt-0.5">{offerSelectorMeta(offer)}</p>
      </div>
    </div>
  );
}

export function GetLinkModal({
  lockedOffer,
  onClose,
}: {
  lockedOffer?: LinkOfferOption | null;
  onClose: () => void;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string>(lockedOffer ? String(lockedOffer.id) : '');
  const [name, setName] = useState('');
  const [source, setSource] = useState('');
  const [notes, setNotes] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedLink | null>(null);

  const {
    data: offersData,
    isLoading: offersLoading,
    isError: offersError,
    refetch,
  } = useQuery<OffersResponse>({
    queryKey: ['partner', 'offers', 'my'],
    queryFn: () => api.get('/partner/offers'),
    enabled: !lockedOffer,
  });

  const eligibleOffers = useMemo(
    () => (offersData?.items || []).filter(isEligibleOffer),
    [offersData],
  );

  const selectedOffer = lockedOffer
    || eligibleOffers.find((offer) => String(offer.id) === selectedId)
    || null;

  const trafficOptions = useMemo(
    () => trafficOptionsForOffer(selectedOffer),
    [selectedOffer],
  );

  useEffect(() => {
    if (!trafficOptions.length) {
      setSource('');
      return;
    }
    setSource((current) =>
      trafficOptions.some((item) => item.value === current) ? current : trafficOptions[0].value,
    );
  }, [selectedOffer?.id, trafficOptions]);

  const createLink = useMutation({
    mutationFn: () =>
      api.post<CreatedLink>('/partner/links', {
        offer_id: Number(selectedOffer?.id),
        name: name.trim(),
        traffic_source: source,
        notes: notes.trim() || null,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'links'] });
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      setFormError(null);
      setCreated(data);
    },
    onError: (error) => {
      setFormError(createLinkErrorMessage(error));
    },
  });

  const copy = async (url: string) => {
    await navigator.clipboard.writeText(url);
    addToast('Ссылка скопирована', 'success');
  };

  const canSubmit = Boolean(selectedOffer && name.trim() && source && !createLink.isPending);
  const successOfferName = created?.offer_name || selectedOffer?.name || '';
  const createdUrl = created?.short_code ? publicTrackingUrl(created.short_code) : created?.url || '';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          {created ? (
            <div className="flex items-center gap-2">
              <CheckCircle2 size={18} className="text-success" />
              <h2 className="ui-section-title">Ссылка создана</h2>
            </div>
          ) : (
            <h2 className="ui-section-title">Получить ссылку</h2>
          )}
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>

        {created ? (
          <div className="space-y-4">
            {successOfferName && <p className="text-sm font-medium">{successOfferName}</p>}
            <div>
              <p className="text-sm font-medium">{created.name}</p>
              {created.traffic_source && (
                <p className="text-sm text-muted-foreground mt-0.5">{trafficLabel(created.traffic_source)}</p>
              )}
            </div>
            <div>
              <p className="ui-label">Ваша ссылка</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-sm bg-muted px-3 py-2 rounded-md break-all">
                  {createdUrl}
                </code>
                <Button onClick={() => copy(createdUrl)}>Copy</Button>
              </div>
            </div>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CheckCircle2 size={14} />
              Кампания создана автоматически
            </p>
            <div className="flex justify-end">
              <Button onClick={onClose}>Готово</Button>
            </div>
          </div>
        ) : lockedOffer ? (
          <CreateForm
            offerField={
              <div>
                <p className="ui-label">Оффер</p>
                <div className="rounded-md border bg-muted/40 px-3 py-2">
                  <OfferContextRow offer={lockedOffer} />
                </div>
              </div>
            }
            name={name}
            setName={setName}
            source={source}
            setSource={setSource}
            notes={notes}
            setNotes={setNotes}
            trafficOptions={trafficOptions}
            formError={formError}
            canSubmit={canSubmit}
            pending={createLink.isPending}
            onCancel={onClose}
            onSubmit={() => createLink.mutate()}
          />
        ) : offersLoading ? (
          <Skeleton className="h-48 rounded-lg" />
        ) : offersError ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Не удалось загрузить офферы.</p>
            <Button variant="secondary" onClick={() => refetch()}>
              Повторить
            </Button>
          </div>
        ) : !eligibleOffers.length ? (
          <div className="space-y-3">
            <p className="text-sm font-medium">Нет офферов, доступных для продвижения.</p>
            <p className="text-sm text-muted-foreground">
              Перейдите в каталог офферов, чтобы выбрать предложение.
            </p>
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
          <CreateForm
            offerField={
              <div className="relative">
                <span className="ui-label">Оффер *</span>
                <button
                  type="button"
                  className="ui-input h-auto min-h-10 py-2 flex items-center justify-between gap-2 text-left"
                  onClick={() => setSelectorOpen((open) => !open)}
                >
                  {selectedOffer ? (
                    <OfferContextRow offer={selectedOffer} />
                  ) : (
                    <span className="text-muted-foreground">Выберите оффер</span>
                  )}
                  <ChevronDown size={16} className="text-muted-foreground shrink-0" />
                </button>
                {selectorOpen && (
                  <div className="absolute z-10 mt-1 w-full ui-card p-1 max-h-56 overflow-auto">
                    {eligibleOffers.map((offer) => (
                      <button
                        key={offer.id}
                        type="button"
                        className={cn(
                          'w-full rounded-md px-2 py-2 text-left hover:bg-muted/60',
                          String(offer.id) === selectedId && 'bg-muted/60',
                        )}
                        onClick={() => {
                          setSelectedId(String(offer.id));
                          setSelectorOpen(false);
                        }}
                      >
                        <OfferContextRow offer={offer} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            }
            name={name}
            setName={setName}
            source={source}
            setSource={setSource}
            notes={notes}
            setNotes={setNotes}
            trafficOptions={trafficOptions}
            formError={formError}
            canSubmit={canSubmit}
            pending={createLink.isPending}
            onCancel={onClose}
            onSubmit={() => createLink.mutate()}
          />
        )}
      </div>
    </div>
  );
}

function CreateForm({
  offerField,
  name,
  setName,
  source,
  setSource,
  notes,
  setNotes,
  trafficOptions,
  formError,
  canSubmit,
  pending,
  onCancel,
  onSubmit,
}: {
  offerField: ReactNode;
  name: string;
  setName: (value: string) => void;
  source: string;
  setSource: (value: string) => void;
  notes: string;
  setNotes: (value: string) => void;
  trafficOptions: (typeof TRAFFIC_TYPES)[number][];
  formError: string | null;
  canSubmit: boolean;
  pending: boolean;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="space-y-4">
      {offerField}
      <label className="block">
        <span className="ui-label">Название ссылки *</span>
        <input
          className="ui-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Telegram — основной канал"
        />
      </label>
      <label className="block">
        <span className="ui-label">Источник трафика *</span>
        <select
          className="ui-input"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          disabled={!trafficOptions.length}
        >
          {!trafficOptions.length && <option value="">Выберите оффер</option>}
          {trafficOptions.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="ui-label">Заметка</span>
        <textarea
          className="ui-input min-h-[72px] h-auto py-2"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Основная ссылка в закреплённом Telegram-посте."
        />
      </label>
      <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
        <Info size={14} className="mt-0.5 shrink-0" />
        Кампания будет создана автоматически.
      </p>
      {formError && <p className="text-sm text-destructive">{formError}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          Отмена
        </Button>
        <Button disabled={!canSubmit} onClick={onSubmit}>
          {pending ? 'Создание...' : 'Создать ссылку'}
        </Button>
      </div>
    </div>
  );
}
