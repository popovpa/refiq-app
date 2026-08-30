import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeftRight, MousePointerClick, Percent, Wallet } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { StatCard } from '@/shared/components/StatCard';
import { useToast } from '@/shared/components/Toast';
import { BusinessLinkDetailDrawer, type BusinessPromotionLink } from '@/shared/links/BusinessLinkDetailDrawer';
import { EditDestinationModal } from '@/shared/links/EditDestinationModal';
import { cn } from '@/shared/utils/cn';
import { formatCommission, formatMoney, formatNumber } from '@/shared/utils/format';
import { OfferImage } from '@/shared/offers/OfferImage';
import { OfferAiSplitButton } from '@/shared/offers/OfferAiSplitButton';
import { OfferCreativesTab } from '@/shared/creatives/OfferCreativesTab';
import {
  ATTRIBUTION_MODEL_LABEL,
  accessLabel,
  conversionLabel,
  statusBadge,
  tabClass,
  trafficLabel,
} from '@/shared/offers/labels';
import { OfferOverview, OfferOverviewSkeleton, offerKpiTrends } from './OfferOverview';
import type { BusinessOfferDetailData } from './offerDetailTypes';

const partnerStatus: Record<string, { label: string; className: string }> = {
  approved: { label: 'Активен', className: 'bg-accent text-primary' },
  pending: { label: 'Заявка', className: 'bg-yellow-50 text-yellow-700' },
  rejected: { label: 'Отклонена', className: 'bg-red-50 text-red-700' },
  cancelled: { label: 'Отменена', className: 'bg-muted text-muted-foreground' },
};

export function BusinessOfferDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'overview' | 'partners' | 'terms' | 'promotion' | 'materials'>('overview');
  const [partnerFilter, setPartnerFilter] = useState<'all' | 'approved' | 'pending'>('all');
  const [confirm, setConfirm] = useState<'pause' | 'resume' | 'archive' | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [selectedLink, setSelectedLink] = useState<BusinessPromotionLink | null>(null);
  const [editDestination, setEditDestination] = useState(false);

  const { data: offer, isLoading } = useQuery<BusinessOfferDetailData>({
    queryKey: ['business', 'offers', id],
    queryFn: () => api.get(`/business/offers/${id}`),
    enabled: !!id,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['business', 'offers', id] });

  const updateStatus = useMutation({
    mutationFn: (status: string) => api.patch(`/business/offers/${id}`, { status }),
    onSuccess: () => {
      invalidate();
      addToast('Статус обновлён', 'success');
      setConfirm(null);
    },
    onError: () => addToast('Не удалось изменить статус', 'error'),
  });

  const decide = useMutation({
    mutationFn: ({ accessId, action }: { accessId: number; action: 'approve' | 'reject' }) =>
      api.post(`/business/offers/${id}/partners/${accessId}/${action}`),
    onSuccess: () => {
      invalidate();
      addToast('Заявка обработана', 'success');
    },
    onError: () => addToast('Не удалось обработать заявку', 'error'),
  });

  const invite = useMutation({
    mutationFn: () => api.post(`/business/offers/${id}/invite`, { email: inviteEmail.trim() }),
    onSuccess: () => {
      invalidate();
      setInviteOpen(false);
      setInviteEmail('');
      addToast('Приглашение отправлено', 'success');
    },
    onError: () => addToast('Партнёр не найден', 'error'),
  });

  const partners = useMemo(() => {
    const rows = offer?.partners || [];
    if (partnerFilter === 'all') return rows;
    return rows.filter((row) => row.status === partnerFilter);
  }, [offer, partnerFilter]);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-14 rounded-xl" />
        <div className="grid grid-cols-2 xl:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-[88px] rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-8 w-80 rounded-md" />
        <OfferOverviewSkeleton />
      </div>
    );
  }

  if (!offer) {
    return (
      <div className="text-center py-16">
        <p className="text-muted-foreground">Оффер не найден</p>
      </div>
    );
  }

  const status = statusBadge(offer.status);
  const rule = offer.commission_rules?.[0];
  const trends = offerKpiTrends(offer.timeseries);

  return (
    <div className="space-y-3">
      <button type="button" onClick={() => navigate('/business/offers')} className="text-sm text-muted-foreground hover:text-primary">
        ← Офферы
      </button>

      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <OfferImage src={offer.image_url} name={offer.name} size="md" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="ui-page-title truncate">{offer.name}</h1>
              <span className={cn('ui-badge', status.className)}>{status.label}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-0.5">
              {offer.category || 'Без категории'} · {accessLabel(offer.access_policy)} · {formatCommission(rule)}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <OfferAiSplitButton
            label="Изменить с AI"
            onPrimary={() => navigate(`/business/offers/${id}/edit?ai=1`)}
            items={[
              {
                id: 'ai',
                label: 'Изменить с AI',
                ai: true,
                onSelect: () => navigate(`/business/offers/${id}/edit?ai=1`),
              },
              {
                id: 'manual',
                label: 'Редактировать вручную',
                onSelect: () => navigate(`/business/offers/${id}/edit`),
              },
            ]}
          />
          {offer.status === 'active' && (
            <Button variant="secondary" onClick={() => setConfirm('pause')}>
              Приостановить
            </Button>
          )}
          {offer.status === 'paused' && (
            <Button variant="secondary" onClick={() => setConfirm('resume')}>
              Возобновить
            </Button>
          )}
          {offer.status !== 'archived' && (
            <Button variant="ghost" onClick={() => setConfirm('archive')}>
              Архивировать
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-5 gap-3">
        <StatCard className="p-3" title="Клики" value={formatNumber(offer.kpis.clicks)} icon={MousePointerClick} tone="blue" trend={trends.clicks} />
        <StatCard className="p-3" title="Конверсии" value={formatNumber(offer.kpis.conversions)} icon={ArrowLeftRight} tone="teal" trend={trends.conversions} />
        <StatCard className="p-3" title="CR" value={`${formatNumber(offer.kpis.cr)}%`} icon={Percent} tone="purple" trend={trends.cr} />
        <StatCard className="p-3" title="Выручка" value={formatMoney(offer.kpis.revenue)} icon={Wallet} tone="green" />
        <StatCard className="p-3" title="Комиссии партнёрам" value={formatMoney(offer.kpis.commissions)} icon={Wallet} tone="orange" />
      </div>

      <div className="flex gap-1 bg-muted rounded-md p-0.5 w-fit">
        {[
          { key: 'overview', label: 'Обзор' },
          { key: 'partners', label: 'Партнёры' },
          { key: 'terms', label: 'Условия' },
          { key: 'promotion', label: 'Продвижение' },
          { key: 'materials', label: 'Материалы' },
        ].map((item) => (
          <button key={item.key} type="button" className={tabClass(tab === item.key)} onClick={() => setTab(item.key as typeof tab)}>
            {item.label}
          </button>
        ))}
      </div>

      {id && tab !== 'materials' && <OfferCreativesTab offerId={id} variant="banner" />}

      {tab === 'overview' && (
        <OfferOverview
          offer={offer}
          onOpenPartners={(filter) => {
            setPartnerFilter(filter || 'all');
            setTab('partners');
          }}
          onOpenPromotion={() => setTab('promotion')}
        />
      )}

      {tab === 'partners' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-1 bg-muted rounded-md p-0.5 w-fit">
              {[
                { key: 'all', label: 'Все' },
                { key: 'approved', label: 'Активные' },
                { key: 'pending', label: 'Заявки' },
              ].map((item) => (
                <button key={item.key} type="button" className={tabClass(partnerFilter === item.key)} onClick={() => setPartnerFilter(item.key as typeof partnerFilter)}>
                  {item.label}
                </button>
              ))}
            </div>
            <Button size="sm" onClick={() => setInviteOpen(true)}>
              + Пригласить партнёра
            </Button>
          </div>
          <div className="ui-card overflow-x-auto">
            <table className="ui-table">
              <thead>
                <tr>
                  <th>Партнёр</th>
                  <th>Статус</th>
                  <th className="text-right">Клики</th>
                  <th className="text-right">Конверсии</th>
                  <th className="text-right">CR</th>
                  <th className="text-right">Комиссии</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {partners.map((row) => {
                  const badge = partnerStatus[row.status] || partnerStatus.pending;
                  return (
                    <tr key={row.id}>
                      <td>
                        <p className="font-medium">{row.name}</p>
                        <p className="text-xs text-muted-foreground">{row.email}</p>
                        {row.status === 'pending' && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {[row.geo, row.topics, (row.traffic_sources || []).join(', ')].filter(Boolean).join(' · ')}
                            {row.comment ? ` · ${row.comment}` : ''}
                          </p>
                        )}
                      </td>
                      <td>
                        <span className={cn('ui-badge', badge.className)}>{badge.label}</span>
                      </td>
                      <td className="text-right">{formatNumber(row.clicks)}</td>
                      <td className="text-right">{formatNumber(row.conversions)}</td>
                      <td className="text-right">{formatNumber(row.cr)}%</td>
                      <td className="text-right">{formatMoney(row.commissions)}</td>
                      <td className="text-right">
                        {row.status === 'pending' && (
                          <div className="inline-flex gap-2">
                            <Button size="sm" variant="secondary" onClick={() => decide.mutate({ accessId: row.id, action: 'reject' })}>
                              Отклонить
                            </Button>
                            <Button size="sm" onClick={() => decide.mutate({ accessId: row.id, action: 'approve' })}>
                              Одобрить
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'terms' && (
        <div className="ui-card p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="ui-section-title">Условия</h2>
            <Button size="sm" variant="secondary" onClick={() => navigate(`/business/offers/${id}/edit?focus=terms`)}>
              Редактировать условия
            </Button>
          </div>
          <div className="grid sm:grid-cols-2 gap-4 text-sm">
            <Info label="Conversion goal" value={conversionLabel(offer.conversion_type)} />
            <Info label="Комиссия" value={formatCommission(rule)} />
            <Info label="Attribution window" value={`${offer.attribution_window_days} дн.`} />
            <Info label="Модель атрибуции" value={offer.attribution_model || ATTRIBUTION_MODEL_LABEL} />
            <Info label="Доступ" value={accessLabel(offer.access_policy)} />
            <Info label="GEO" value={offer.geo || '—'} />
            <Info label="Разрешённый трафик" value={(offer.allowed_traffic || []).map(trafficLabel).join(', ') || '—'} />
            <Info label="Запрещённый трафик" value={(offer.forbidden_traffic || []).map(trafficLabel).join(', ') || '—'} />
          </div>
          {offer.partner_notes && (
            <div>
              <p className="text-sm text-muted-foreground">Комментарий партнёрам</p>
              <p className="text-sm mt-1">{offer.partner_notes}</p>
            </div>
          )}
        </div>
      )}

      {tab === 'promotion' && (
        <div className="ui-card overflow-x-auto">
          <div className="px-4 py-3 text-sm text-muted-foreground">
            Активные партнёры: {formatNumber(offer.active_partners)} · Активные ссылки: {formatNumber(offer.active_links)}
          </div>
          <table className="ui-table">
            <thead>
              <tr>
                <th>Партнёр</th>
                <th>Ссылка</th>
                <th>Источник</th>
                <th className="text-right">Клики</th>
                <th className="text-right">Конверсии</th>
              </tr>
            </thead>
            <tbody>
              {offer.promotion_links.map((link) => (
                <tr
                  key={link.id}
                  className="cursor-pointer"
                  onClick={() => setSelectedLink(link)}
                >
                  <td className="font-medium">{link.partner_name || link.name}</td>
                  <td>
                    <code className="text-xs bg-muted px-2 py-1 rounded-md">{link.url}</code>
                  </td>
                  <td>{link.traffic_source ? trafficLabel(link.traffic_source) : '—'}</td>
                  <td className="text-right">{formatNumber(link.clicks)}</td>
                  <td className="text-right">{formatNumber(link.conversions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'materials' && id && (
        <OfferCreativesTab offerId={id} variant="full" onCreateTrackingLink={() => setTab('promotion')} />
      )}

      {selectedLink && id && (
        <BusinessLinkDetailDrawer
          offerId={id}
          link={selectedLink}
          onClose={() => {
            setSelectedLink(null);
            setEditDestination(false);
          }}
          onEditDestination={() => setEditDestination(true)}
        />
      )}

      {selectedLink && editDestination && id && (
        <EditDestinationModal
          offerId={id}
          linkId={String(selectedLink.id)}
          shortCode={selectedLink.short_code || selectedLink.url.split('/').pop() || ''}
          currentUrl={selectedLink.destination_url || ''}
          status={selectedLink.status}
          onClose={() => setEditDestination(false)}
          onUpdated={(destinationUrl) => {
            setSelectedLink((current) => (current ? { ...current, destination_url: destinationUrl } : current));
            queryClient.setQueryData(['business', 'offers', id], (current: BusinessOfferDetailData | undefined) => {
              if (!current) return current;
              return {
                ...current,
                promotion_links: current.promotion_links.map((item) =>
                  String(item.id) === String(selectedLink.id) ? { ...item, destination_url: destinationUrl } : item,
                ),
              };
            });
            queryClient.invalidateQueries({
              queryKey: ['business', 'offers', id, 'links', selectedLink.id, 'destination-history'],
            });
          }}
        />
      )}

      {inviteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-foreground/30" onClick={() => setInviteOpen(false)} />
          <div className="relative ui-card w-full max-w-md p-5 space-y-4 shadow-soft">
            <h2 className="ui-section-title">Пригласить партнёра</h2>
            <label className="block">
              <span className="ui-label">Email партнёра</span>
              <input className="ui-input" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="partner@example.com" />
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setInviteOpen(false)}>
                Отмена
              </Button>
              <Button disabled={!inviteEmail.trim() || invite.isPending} onClick={() => invite.mutate()}>
                Отправить приглашение
              </Button>
            </div>
          </div>
        </div>
      )}

      {confirm === 'pause' && (
        <ConfirmDialog title="Приостановить оффер" confirmLabel="Приостановить" pending={updateStatus.isPending} onClose={() => setConfirm(null)} onConfirm={() => updateStatus.mutate('paused')}>
          <p>Новые партнёры не подключаются, новые ссылки не создаются, новый трафик останавливается.</p>
          <p>Исторические данные сохраняются. Существующие допустимые клики и конверсии продолжают обрабатываться согласно attribution window.</p>
        </ConfirmDialog>
      )}
      {confirm === 'resume' && (
        <ConfirmDialog title="Возобновить оффер" confirmLabel="Возобновить" pending={updateStatus.isPending} onClose={() => setConfirm(null)} onConfirm={() => updateStatus.mutate('active')}>
          <p>Оффер снова будет доступен партнёрам, можно создавать ссылки и принимать новый трафик.</p>
        </ConfirmDialog>
      )}
      {confirm === 'archive' && (
        <ConfirmDialog title="Архивировать оффер" confirmLabel="Архивировать" pending={updateStatus.isPending} onClose={() => setConfirm(null)} onConfirm={() => updateStatus.mutate('archived')}>
          <p>Архивирование не удаляет оффер. Клики, конверсии, партнёры, комиссии, выплаты и история условий сохраняются.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="font-medium mt-0.5">{value}</p>
    </div>
  );
}
