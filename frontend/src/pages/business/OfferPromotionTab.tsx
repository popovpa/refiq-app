import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { formatMoney, formatNumber } from '@/shared/utils/format';
import { partnerDisplayName } from '@/shared/partners/displayName';
import { displayTrackingUrl, publicTrackingUrl } from '@/shared/offers/trackingLink';
import { linkStatusClass, linkStatusLabel } from '@/shared/partner/links/types';
import { cn } from '@/shared/utils/cn';
import type { BusinessPromotionLink } from '@/shared/links/BusinessLinkDetailDrawer';
import { BusinessLinkDetailDrawer } from '@/shared/links/BusinessLinkDetailDrawer';
import { EditDestinationModal } from '@/shared/links/EditDestinationModal';
import { CreateBusinessCampaignModal } from '@/shared/promotion/CreateBusinessCampaignModal';
import { CreateBusinessLinkModal } from '@/shared/promotion/CreateBusinessLinkModal';
import type { TrafficSplit } from '@/pages/business/offerDetailTypes';

export type BusinessCampaign = {
  id: number;
  name: string;
  description?: string | null;
  status: 'ACTIVE' | 'ARCHIVED';
  links_count: number;
  clicks: number;
  conversions_count: number;
  cr: number;
};

export type BusinessOwnLink = {
  id: number;
  name?: string | null;
  url: string;
  short_code: string;
  destination_url: string;
  campaign_id?: number | null;
  campaign_name?: string | null;
  owner_type?: string;
  status: string;
  stats?: { clicks: number; conversions: number };
};

type CampaignsResponse = { items: BusinessCampaign[] };
type LinksResponse = { items: BusinessOwnLink[] };

export function OfferPromotionTab({
  offerId,
  offerStatus,
  trafficSplit,
  partnerLinks,
  onOpenPartnerLink,
  autoOpenCreateLink = false,
}: {
  offerId: string;
  offerStatus: string;
  trafficSplit?: TrafficSplit;
  partnerLinks: BusinessPromotionLink[];
  onOpenPartnerLink: (link: BusinessPromotionLink) => void;
  autoOpenCreateLink?: boolean;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [campaignModal, setCampaignModal] = useState<BusinessCampaign | 'new' | null>(null);
  const [linkModal, setLinkModal] = useState(autoOpenCreateLink);
  const [selectedOwnLink, setSelectedOwnLink] = useState<BusinessOwnLink | null>(null);
  const [editDestination, setEditDestination] = useState(false);
  const canPromote = offerStatus === 'active';

  const campaignsQuery = useQuery<CampaignsResponse>({
    queryKey: ['business', 'offers', offerId, 'campaigns'],
    queryFn: () => api.get(`/business/offers/${offerId}/campaigns`),
  });
  const ownLinksQuery = useQuery<LinksResponse>({
    queryKey: ['business', 'offers', offerId, 'own-links'],
    queryFn: () => api.get(`/business/offers/${offerId}/links`),
  });

  const campaigns = campaignsQuery.data?.items || [];
  const ownLinks = ownLinksQuery.data?.items || [];
  const activeCampaigns = useMemo(
    () => campaigns.filter((item) => item.status === 'ACTIVE'),
    [campaigns],
  );

  const archiveCampaign = useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'ACTIVE' | 'ARCHIVED' }) =>
      api.patch(`/business/offers/${offerId}/campaigns/${id}`, { status }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'campaigns'] });
      addToast(variables.status === 'ARCHIVED' ? 'Кампания в архиве' : 'Кампания восстановлена', 'success');
    },
    onError: () => addToast('Не удалось изменить кампанию', 'error'),
  });

  const toggleLink = useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'ACTIVE' | 'DISABLED' }) =>
      api.patch(`/business/offers/${offerId}/links/${id}/status`, { status }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'own-links'] });
      queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId] });
      addToast(variables.status === 'DISABLED' ? 'Ссылка отключена' : 'Ссылка включена', 'success');
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      addToast(apiError?.error?.message || 'Не удалось изменить ссылку', 'error');
    },
  });

  const copyUrl = async (shortCode: string) => {
    await navigator.clipboard.writeText(publicTrackingUrl(shortCode));
    addToast('Ссылка скопирована', 'success');
  };

  const toDrawerLink = (link: BusinessOwnLink): BusinessPromotionLink => ({
    id: link.id,
    name: link.name,
    url: link.url,
    short_code: link.short_code,
    destination_url: link.destination_url,
    status: link.status,
    clicks: link.stats?.clicks || 0,
    conversions: link.stats?.conversions || 0,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId] });
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'campaigns'] });
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'own-links'] });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Собственное продвижение оффера без партнёра и комиссии.</p>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" disabled={!canPromote} onClick={() => setCampaignModal('new')}>
            Создать кампанию
          </Button>
          <Button size="sm" disabled={!canPromote} onClick={() => setLinkModal(true)}>
            <Plus size={14} />
            Создать ссылку
          </Button>
        </div>
      </div>

      {trafficSplit && (
        <div className="grid sm:grid-cols-2 gap-3">
          <TrafficCard title="Свой трафик" stats={trafficSplit.own} />
          <TrafficCard title="Партнёрский трафик" stats={trafficSplit.partner} showCommissions />
        </div>
      )}

      <section className="ui-card overflow-x-auto">
        <div className="px-4 py-3 border-b border-border/70">
          <h2 className="ui-section-title">Кампании</h2>
        </div>
        {campaigns.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">Кампаний пока нет. Ссылку можно создать без кампании.</p>
        ) : (
          <table className="ui-table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Статус</th>
                <th className="text-right">Ссылки</th>
                <th className="text-right">Клики</th>
                <th className="text-right">Конверсии</th>
                <th className="text-right">CR</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {campaigns.map((campaign) => (
                <tr key={campaign.id}>
                  <td className="font-medium">
                    <div>{campaign.name}</div>
                    {campaign.description && (
                      <p className="text-xs text-muted-foreground mt-0.5">{campaign.description}</p>
                    )}
                  </td>
                  <td>
                    <span className={cn('ui-badge', campaign.status === 'ACTIVE' ? 'bg-accent text-primary' : 'bg-muted text-muted-foreground')}>
                      {campaign.status === 'ACTIVE' ? 'Активна' : 'В архиве'}
                    </span>
                  </td>
                  <td className="text-right">{formatNumber(campaign.links_count)}</td>
                  <td className="text-right">{formatNumber(campaign.clicks)}</td>
                  <td className="text-right">{formatNumber(campaign.conversions_count)}</td>
                  <td className="text-right">{formatNumber(campaign.cr)}%</td>
                  <td className="text-right">
                    <div className="inline-flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setCampaignModal(campaign)}>
                        Изменить
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={archiveCampaign.isPending}
                        onClick={() =>
                          archiveCampaign.mutate({
                            id: campaign.id,
                            status: campaign.status === 'ACTIVE' ? 'ARCHIVED' : 'ACTIVE',
                          })
                        }
                      >
                        {campaign.status === 'ACTIVE' ? 'В архив' : 'Восстановить'}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="ui-card overflow-x-auto">
        <div className="px-4 py-3 border-b border-border/70">
          <h2 className="ui-section-title">Мои ссылки</h2>
        </div>
        {ownLinks.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">Собственных ссылок пока нет.</p>
        ) : (
          <table className="ui-table">
            <thead>
              <tr>
                <th>Ссылка</th>
                <th>Кампания</th>
                <th>Целевая страница</th>
                <th>Статус</th>
                <th className="text-right">Клики</th>
                <th className="text-right">Конверсии</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {ownLinks.map((link) => (
                <tr
                  key={link.id}
                  className="cursor-pointer"
                  onClick={() => {
                    setSelectedOwnLink(link);
                    setEditDestination(false);
                  }}
                >
                  <td>
                    <button
                      type="button"
                      className="text-left"
                      onClick={(event) => {
                        event.stopPropagation();
                        copyUrl(link.short_code);
                      }}
                    >
                      <code className="text-xs bg-muted px-2 py-1 rounded-md">{displayTrackingUrl(link.short_code)}</code>
                    </button>
                    {link.name && <p className="text-xs text-muted-foreground mt-1">{link.name}</p>}
                  </td>
                  <td>{link.campaign_name || 'Без кампании'}</td>
                  <td className="max-w-[220px] truncate" title={link.destination_url}>
                    {link.destination_url}
                  </td>
                  <td>
                    <span className={cn('ui-badge', linkStatusClass(link.status))}>{linkStatusLabel(link.status)}</span>
                  </td>
                  <td className="text-right">{formatNumber(link.stats?.clicks || 0)}</td>
                  <td className="text-right">{formatNumber(link.stats?.conversions || 0)}</td>
                  <td className="text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={toggleLink.isPending || (link.status !== 'ACTIVE' && !canPromote)}
                      onClick={(event) => {
                        event.stopPropagation();
                        toggleLink.mutate({
                          id: link.id,
                          status: link.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE',
                        });
                      }}
                    >
                      {link.status === 'ACTIVE' ? 'Отключить' : 'Включить'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="ui-card overflow-x-auto">
        <div className="px-4 py-3 border-b border-border/70">
          <h2 className="ui-section-title">Ссылки партнёров</h2>
          <p className="text-sm text-muted-foreground mt-1">Только просмотр. Управление — в карточке партнёрской ссылки.</p>
        </div>
        {partnerLinks.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">Партнёры ещё не создали ссылки.</p>
        ) : (
          <table className="ui-table">
            <thead>
              <tr>
                <th>Партнёр</th>
                <th>Ссылка</th>
                <th className="text-right">Клики</th>
                <th className="text-right">Конверсии</th>
              </tr>
            </thead>
            <tbody>
              {partnerLinks.map((link) => (
                <tr key={link.id} className="cursor-pointer" onClick={() => onOpenPartnerLink(link)}>
                  <td className="font-medium">{partnerDisplayName(link.partner_name) || link.name}</td>
                  <td>
                    <code className="text-xs bg-muted px-2 py-1 rounded-md">{link.url}</code>
                  </td>
                  <td className="text-right">{formatNumber(link.clicks)}</td>
                  <td className="text-right">{formatNumber(link.conversions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {campaignModal && (
        <CreateBusinessCampaignModal
          offerId={offerId}
          campaign={campaignModal === 'new' ? null : campaignModal}
          onClose={() => setCampaignModal(null)}
          onCreated={() => {
            invalidate();
            setCampaignModal(null);
          }}
        />
      )}
      {linkModal && (
        <CreateBusinessLinkModal
          offerId={offerId}
          campaigns={activeCampaigns}
          onClose={() => setLinkModal(false)}
          onCreated={() => {
            invalidate();
            setLinkModal(false);
          }}
        />
      )}

      {selectedOwnLink && (
        <BusinessLinkDetailDrawer
          offerId={offerId}
          link={toDrawerLink(selectedOwnLink)}
          variant="own"
          onClose={() => {
            setSelectedOwnLink(null);
            setEditDestination(false);
          }}
          onEditDestination={() => setEditDestination(true)}
        />
      )}

      {selectedOwnLink && editDestination && (
        <EditDestinationModal
          offerId={offerId}
          linkId={String(selectedOwnLink.id)}
          shortCode={selectedOwnLink.short_code}
          currentUrl={selectedOwnLink.destination_url}
          status={selectedOwnLink.status}
          linkLabel="Tracking-ссылка"
          onClose={() => setEditDestination(false)}
          onUpdated={(destinationUrl) => {
            setSelectedOwnLink((current) => (current ? { ...current, destination_url: destinationUrl } : current));
            queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'own-links'] });
            queryClient.invalidateQueries({
              queryKey: ['business', 'offers', offerId, 'links', selectedOwnLink.id, 'destination-history'],
            });
          }}
        />
      )}
    </div>
  );
}

function TrafficCard({
  title,
  stats,
  showCommissions = false,
}: {
  title: string;
  stats: TrafficSplit['own'];
  showCommissions?: boolean;
}) {
  return (
    <div className="ui-card p-4 space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <Metric label="Клики" value={formatNumber(stats.clicks)} />
        <Metric label="Конверсии" value={formatNumber(stats.conversions)} />
        <Metric label="CR" value={`${formatNumber(stats.cr)}%`} />
        <Metric label="Выручка" value={formatMoney(stats.revenue)} />
        {showCommissions && <Metric label="Комиссии" value={formatMoney(stats.commissions)} />}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium tabular-nums">{value}</p>
    </div>
  );
}
