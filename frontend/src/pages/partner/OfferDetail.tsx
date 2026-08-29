import { useMemo, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { Copy, Info, Plus, X } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { formatNumber } from '@/shared/utils/format';
import { OfferImage } from '@/shared/offers/OfferImage';
import { GetLinkModal } from '@/shared/offers/GetLinkModal';
import { RequestAccessModal } from '@/shared/offers/RequestAccessModal';
import { PartnerCreatives } from '@/shared/creatives/PartnerCreatives';
import { displayTrackingUrl, publicTrackingUrl } from '@/shared/offers/trackingLink';
import {
  accessLabel,
  conversionLabel,
  trafficLabel,
} from '@/shared/offers/labels';
import {
  formatCommissionPrimary,
  hasOfferStatData,
} from '@/shared/offers/partnerOfferCardFormat';
import { useAuth } from '@/shared/hooks/useAuth';
import { cn } from '@/shared/utils/cn';

interface Material {
  type: string;
  title?: string;
  content?: string;
  url?: string;
}

interface CommissionRule {
  type: string;
  value: number;
  currency: string | null;
}

const DETAIL_COMMISSION_CONTEXT: Record<string, { percent: string; fixed: string }> = {
  sale: { percent: 'с покупки', fixed: 'за покупку' },
  signup: { percent: 'с подтверждённой регистрации', fixed: 'за подтверждённую регистрацию' },
  lead: { percent: 'с подтверждённого лида', fixed: 'за подтверждённый лид' },
  application: { percent: 'с одобренной заявки', fixed: 'за одобренную заявку' },
  custom: { percent: 'с конверсии', fixed: 'за конверсию' },
};

function formatDetailCommissionContext(
  conversionType: string,
  rule?: CommissionRule | null,
): string {
  if (!rule || rule.value === null || rule.value === undefined) {
    return conversionLabel(conversionType);
  }
  const phrases = DETAIL_COMMISSION_CONTEXT[conversionType] || DETAIL_COMMISSION_CONTEXT.custom;
  return rule.type === 'percent' ? phrases.percent : phrases.fixed;
}

interface OfferStats {
  clicks: number;
  conversions: number;
  cr: number;
  epc: number;
  commissions?: number;
}

interface PartnerOfferDetail {
  id: number;
  name: string;
  description: string | null;
  image_url?: string | null;
  category?: string | null;
  geo?: string | null;
  status?: string;
  access_policy: string;
  conversion_type: string;
  attribution_window_days: number;
  attribution_model?: string;
  allowed_traffic?: string[];
  forbidden_traffic?: string[];
  partner_notes?: string | null;
  materials?: Material[];
  partner_status?: string | null;
  commission_rules: CommissionRule[];
  clicks?: number;
  conversions?: number;
  cr?: number;
  epc?: number;
  my_stats?: OfferStats | null;
  partner_profile?: { name?: string | null; email?: string | null };
}

interface LinkItem {
  id: number | string;
  offer_id: number | string;
  name?: string | null;
  short_code: string;
  url: string;
  traffic_source?: string | null;
  status: string;
}

const ATTRIBUTION_RULE_LABEL = 'Последний допустимый партнёрский переход';
const ATTRIBUTION_TOOLTIP =
  'Если перед конверсией было несколько допустимых партнёрских переходов, конверсия относится к последнему из них, попадающему в окно атрибуции.';

const GEO_NAMES: Record<string, string> = {
  RU: 'Россия',
  KZ: 'Казахстан',
  BY: 'Беларусь',
  WW: 'Весь мир',
  UA: 'Украина',
  US: 'США',
  EU: 'Европа',
};

const FORBIDDEN_TRAFFIC_LABELS: Record<string, string> = {
  motivated: 'Мотивированный трафик',
  brand_bidding: 'Brand bidding',
  cashback: 'Cashback',
  ppc: 'PPC',
};

function formatGeo(geo?: string | null): string {
  if (!geo) return '—';
  return geo
    .split(/[,;]+/)
    .map((part) => {
      const code = part.trim();
      return GEO_NAMES[code] || code;
    })
    .filter(Boolean)
    .join(', ');
}

function forbiddenTrafficLabel(value: string): string {
  return FORBIDDEN_TRAFFIC_LABELS[value] || trafficLabel(value);
}

function partnerStatusBadge(
  joined: boolean,
  pending: boolean,
  accessPolicy: string,
): { label: string; className: string } {
  if (joined) {
    return { label: 'Доступ предоставлен', className: 'bg-accent text-primary' };
  }
  if (pending) {
    return { label: 'Заявка рассматривается', className: 'bg-yellow-50 text-yellow-700' };
  }
  if (accessPolicy === 'open') {
    return { label: 'Публичный', className: 'bg-accent text-primary' };
  }
  if (accessPolicy === 'approval') {
    return { label: 'Требуется одобрение', className: 'bg-yellow-50 text-yellow-700' };
  }
  return { label: 'Только по приглашению', className: 'bg-muted text-muted-foreground' };
}

function formatCommissionLine(rule: CommissionRule | undefined, conversionType: string): string {
  const primary = formatCommissionPrimary(rule);
  if (primary === '—') return primary;
  return `${primary} ${formatDetailCommissionContext(conversionType, rule)}`;
}

function pluralize(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

function linkLabel(link: LinkItem): string {
  if (link.name?.trim()) return link.name.trim();
  if (link.traffic_source) return trafficLabel(link.traffic_source);
  return 'Партнёрская ссылка';
}

export function PartnerOfferDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [linkOpen, setLinkOpen] = useState(false);
  const [requestOpen, setRequestOpen] = useState(false);
  const [materialsOpen, setMaterialsOpen] = useState(false);

  const { data: offer, isLoading } = useQuery<PartnerOfferDetail>({
    queryKey: ['partner', 'offers', id],
    queryFn: () => api.get(`/partner/offers/${id}`),
    enabled: !!id,
  });

  const joined = offer?.partner_status === 'approved';
  const pending = offer?.partner_status === 'pending';

  const { data: linksData } = useQuery<{ items: LinkItem[] }>({
    queryKey: ['partner', 'links'],
    queryFn: () => api.get('/partner/links'),
    enabled: !!joined,
  });

  const offerLinks = useMemo(() => {
    if (!linksData?.items || !id) return [];
    return linksData.items.filter(
      (link) => String(link.offer_id) === String(id) && link.status === 'ACTIVE',
    );
  }, [linksData, id]);

  const activeLinksCount = useMemo(() => {
    if (!linksData?.items || !id) return 0;
    return linksData.items.filter(
      (link) => String(link.offer_id) === String(id) && link.status === 'ACTIVE',
    ).length;
  }, [linksData, id]);

  const cancelRequest = useMutation({
    mutationFn: () => api.post(`/partner/offers/${id}/cancel-request`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers', id] });
      addToast('Заявка отменена', 'success');
    },
  });

  const joinOpen = useMutation({
    mutationFn: () => api.post(`/partner/offers/${id}/join`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers', id] });
      addToast('Доступ предоставлен', 'success');
      setLinkOpen(true);
    },
  });

  const copyLink = async (shortCode: string) => {
    await navigator.clipboard.writeText(publicTrackingUrl(shortCode));
    addToast('Ссылка скопирована', 'success');
  };

  if (isLoading) return <Skeleton className="h-full min-h-[480px] rounded-xl" />;
  if (!offer) {
    return <p className="text-muted-foreground">Оффер не найден</p>;
  }

  const partnerName =
    offer.partner_profile?.name ||
    [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
    user?.email ||
    'Партнёр';
  const rule = offer.commission_rules?.[0];
  const statusBadge = partnerStatusBadge(joined, pending, offer.access_policy);
  const hasStats = hasOfferStatData({ clicks: offer.clicks ?? 0 });
  const epc = hasStats
    ? { value: `${formatNumber(offer.epc)} ₽` }
    : { value: '—', title: 'Недостаточно данных для расчёта' };
  const cr = hasStats
    ? { value: `${formatNumber(offer.cr)}%` }
    : { value: '—', title: 'Недостаточно данных для расчёта' };
  const myStats = offer.my_stats;
  const materials = offer.materials || [];
  const hasMaterials = materials.length > 0;
  const canCreateLink =
    joined || (!pending && offer.access_policy === 'open' && !joined);
  const inviteOnlyBlocked = !joined && !pending && offer.access_policy === 'invite_only';

  const openLinkFlow = () => {
    if (joined || offer.access_policy === 'open') {
      if (!joined) {
        joinOpen.mutate();
        return;
      }
      setLinkOpen(true);
      return;
    }
    if (offer.access_policy === 'approval') {
      setRequestOpen(true);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1320px] flex flex-col h-full min-h-0 gap-3 lg:gap-3.5 max-lg:overflow-auto lg:overflow-hidden">
      <button
        type="button"
        onClick={() => navigate('/partner/offers')}
        className="text-sm text-muted-foreground hover:text-primary shrink-0 self-start"
      >
        ← Офферы
      </button>

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 shrink-0">
        <div className="flex items-start gap-3 min-w-0">
          <OfferImage src={offer.image_url} name={offer.name} size="detail" />
          <div className="min-w-0">
            <h1 className="text-lg font-semibold tracking-tight truncate">{offer.name}</h1>
            {offer.category && (
              <p className="text-sm text-muted-foreground mt-0.5">{offer.category}</p>
            )}
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <span className={cn('ui-badge', statusBadge.className)}>{statusBadge.label}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-1.5">
              {formatCommissionLine(rule, offer.conversion_type)} · GEO {formatGeo(offer.geo)}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {joined && <Button onClick={() => setLinkOpen(true)}>Получить ссылку</Button>}
          {pending && (
            <>
              <Button variant="secondary" onClick={() => cancelRequest.mutate()}>
                Отменить заявку
              </Button>
            </>
          )}
          {!joined && !pending && offer.access_policy === 'open' && (
            <Button onClick={() => joinOpen.mutate()} disabled={joinOpen.isPending}>
              Получить ссылку
            </Button>
          )}
          {!joined && !pending && offer.access_policy === 'approval' && (
            <Button onClick={() => setRequestOpen(true)}>Запросить доступ</Button>
          )}
        </div>
      </div>

      {inviteOnlyBlocked && (
        <p className="text-sm text-muted-foreground shrink-0">
          Этот оффер доступен только приглашённым партнёрам.
        </p>
      )}

      {/* KPI row */}
      <div className="ui-card p-4 shrink-0">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4">
          <KpiCell
            label="Комиссия"
            value={formatCommissionPrimary(rule)}
            secondary={formatDetailCommissionContext(offer.conversion_type, rule)}
          />
          <KpiCell label="EPC" value={epc.value} secondary={epc.title ? 'Недостаточно данных' : undefined} />
          <KpiCell label="CR" value={cr.value} secondary={cr.title ? 'Недостаточно данных' : undefined} />
          <KpiCell
            label="Атрибуция"
            value={`${offer.attribution_window_days} ${pluralize(offer.attribution_window_days, 'день', 'дня', 'дней')}`}
            secondary="окно атрибуции"
          />
        </div>
      </div>

      {/* Two columns: what we promote | main conditions */}
      <div className="grid lg:grid-cols-[1.65fr_1fr] gap-3 shrink-0">
        <div className="ui-card p-4">
          <h2 className="ui-section-title mb-2.5">Что продвигаем</h2>
          {offer.description ? (
            <p className="text-sm text-muted-foreground line-clamp-3 leading-snug mb-3">
              {offer.description}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground mb-3">—</p>
          )}
          <dl className="grid sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <InfoRow label="Целевое действие" value={conversionLabel(offer.conversion_type)} />
            <InfoRow label="Категория" value={offer.category || '—'} />
          </dl>
        </div>

        <div className="ui-card p-4">
          <h2 className="ui-section-title mb-2.5">Основные условия</h2>
          <dl className="space-y-2 text-sm">
            <InfoRow
              label="Комиссия"
              value={`${formatCommissionPrimary(rule)} ${formatDetailCommissionContext(offer.conversion_type, rule)}`.trim()}
            />
            <InfoRow label="Целевое действие" value={conversionLabel(offer.conversion_type)} />
            <InfoRow label="GEO" value={formatGeo(offer.geo)} />
            <InfoRow label="Доступ" value={accessLabel(offer.access_policy)} />
            <InfoRow
              label="Атрибуция"
              value={
                <span className="inline-flex items-center gap-1">
                  {`${offer.attribution_window_days} ${pluralize(offer.attribution_window_days, 'день', 'дня', 'дней')}`}
                  <span className="text-muted-foreground">·</span>
                  <span className="text-muted-foreground">{ATTRIBUTION_RULE_LABEL}</span>
                  <span title={ATTRIBUTION_TOOLTIP} className="text-muted-foreground cursor-help">
                    <Info size={14} />
                  </span>
                </span>
              }
            />
          </dl>
        </div>
      </div>

      {/* Promotion rules */}
      <div className="ui-card p-4 shrink-0">
        <h2 className="ui-section-title mb-2.5">Правила продвижения</h2>
        <div className="space-y-2.5 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground shrink-0">Разрешено:</span>
            {(offer.allowed_traffic || []).length ? (
              (offer.allowed_traffic || []).map((item) => (
                <span key={item} className="ui-badge bg-accent text-primary">
                  {trafficLabel(item)}
                </span>
              ))
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground shrink-0">Запрещено:</span>
            {(offer.forbidden_traffic || []).length ? (
              (offer.forbidden_traffic || []).map((item) => (
                <span key={item} className="ui-badge bg-orange-50 text-warning">
                  {forbiddenTrafficLabel(item)}
                </span>
              ))
            ) : (
              <span className="text-muted-foreground">Нет дополнительных ограничений</span>
            )}
          </div>
          {offer.partner_notes && (
            <p className="text-xs text-muted-foreground pt-1 border-t border-border/60">
              {offer.partner_notes}
            </p>
          )}
        </div>
      </div>

      {/* Bottom: My promotion | Materials */}
      <div className="grid lg:grid-cols-[1.65fr_1fr] gap-3 flex-1 min-h-0 pb-0.5">
        <div className="ui-card p-4 flex flex-col min-h-0 overflow-hidden">
          <div className="flex items-center gap-x-3 gap-y-1 mb-2.5 shrink-0 min-w-0 flex-wrap">
            <h2 className="ui-section-title">Моё продвижение</h2>
            {joined && (
              <button
                type="button"
                onClick={() => navigate(`/partner/links?offerId=${offer.id}`)}
                className="text-[13px] text-muted-foreground hover:text-primary shrink-0"
              >
                Все ссылки →
              </button>
            )}
            {canCreateLink && !inviteOnlyBlocked && (
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-[13px] font-medium text-primary hover:bg-accent shrink-0"
                onClick={openLinkFlow}
                disabled={joinOpen.isPending}
              >
                <Plus size={14} />
                Получить новую ссылку
              </Button>
            )}
          </div>

          {joined && activeLinksCount > 0 && myStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3 text-sm shrink-0">
              <MiniStat
                label={`${activeLinksCount} ${pluralize(activeLinksCount, 'активная ссылка', 'активные ссылки', 'активных ссылок')}`}
              />
              <MiniStat label={`${formatNumber(myStats.clicks)} кликов`} />
              <MiniStat label={`${formatNumber(myStats.conversions)} ${pluralize(myStats.conversions, 'конверсия', 'конверсии', 'конверсий')}`} />
              <MiniStat label={`${formatNumber(myStats.commissions ?? 0)} ₽ заработано`} />
            </div>
          )}

          {joined && offerLinks.length > 0 ? (
            <div className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-0.5">
              {offerLinks.map((link) => (
                <div
                  key={link.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/70 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{linkLabel(link)}</p>
                    <p className="text-xs text-muted-foreground font-mono truncate mt-0.5">
                      {displayTrackingUrl(link.short_code)}
                    </p>
                    {myStats && hasOfferStatData(myStats) && activeLinksCount === 1 && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {formatNumber(myStats.clicks)} кликов · {formatNumber(myStats.conversions)}{' '}
                        {pluralize(myStats.conversions, 'конверсия', 'конверсии', 'конверсий')} · CR{' '}
                        {formatNumber(myStats.cr)}%
                      </p>
                    )}
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => copyLink(link.short_code)}>
                    <Copy size={14} />
                    Copy
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex-1 flex flex-col justify-center py-2 min-h-0">
              <p className="text-sm text-muted-foreground">Вы ещё не продвигаете этот оффер.</p>
              <p className="text-sm text-muted-foreground mt-1">
                Создайте первую партнёрскую ссылку, чтобы начать получать трафик и конверсии.
              </p>
            </div>
          )}
        </div>

        <PartnerCreatives
          offerId={String(offer.id)}
          canCreate={joined}
          trackingShortCode={offerLinks[0]?.short_code}
        />
        {hasMaterials && (
          <button
            type="button"
            onClick={() => setMaterialsOpen(true)}
            className="text-sm text-primary hover:underline self-start"
          >
            Старые материалы оффера →
          </button>
        )}
      </div>

      {linkOpen && (
        <GetLinkModal lockedOffer={offer} onClose={() => setLinkOpen(false)} />
      )}
      {requestOpen && (
        <RequestAccessModal offerId={offer.id} partnerName={partnerName} onClose={() => setRequestOpen(false)} />
      )}
      {materialsOpen && (
        <MaterialsModal materials={materials} onClose={() => setMaterialsOpen(false)} />
      )}
    </div>
  );
}

function KpiCell({
  label,
  value,
  secondary,
}: {
  label: string;
  value: string;
  secondary?: string;
}) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tracking-tight mt-0.5">{value}</p>
      {secondary && <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{secondary}</p>}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-0.5 sm:gap-3">
      <dt className="text-muted-foreground shrink-0">{label}</dt>
      <dd className="font-medium sm:text-right">{value}</dd>
    </div>
  );
}

function MiniStat({ label }: { label: string }) {
  return <p className="text-muted-foreground leading-snug">{label}</p>;
}

function MaterialsModal({ materials, onClose }: { materials: Material[]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="ui-card w-full max-w-lg max-h-[80vh] flex flex-col shadow-soft">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border/70 shrink-0">
          <h3 className="ui-section-title">Материалы для продвижения</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Закрыть"
          >
            <X size={18} />
          </button>
        </div>
        <div className="overflow-auto p-5 space-y-3">
          {materials.map((item, index) => (
            <div key={`${item.title}-${index}`} className="rounded-lg border border-border/70 p-3 space-y-1.5">
              <p className="text-sm font-medium">{item.title || 'Материал'}</p>
              {item.content && <p className="text-sm text-muted-foreground">{item.content}</p>}
              {item.url && (
                <a href={item.url} className="text-sm text-primary hover:underline" target="_blank" rel="noreferrer">
                  Открыть
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
