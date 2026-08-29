import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { useToast } from '@/shared/components/Toast';
import { PartnerOfferCard } from '@/shared/offers/PartnerOfferCard';
import { GetLinkModal } from '@/shared/offers/GetLinkModal';
import { RequestAccessModal } from '@/shared/offers/RequestAccessModal';
import {
  ACCESS_OPTIONS,
  CATEGORIES,
  GEO_OPTIONS,
  tabClass,
} from '@/shared/offers/labels';
import type { OfferListItem } from '@/shared/offers/types';
import { useAuth } from '@/shared/hooks/useAuth';

interface OffersResponse {
  items: OfferListItem[];
}

export function PartnerOffers() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'all' | 'available' | 'mine' | 'pending'>('all');
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('');
  const [geo, setGeo] = useState('');
  const [access, setAccess] = useState('');
  const [linkOffer, setLinkOffer] = useState<OfferListItem | null>(null);
  const [requestOffer, setRequestOffer] = useState<OfferListItem | null>(null);

  const catalogParams = useMemo(() => {
    const search = new URLSearchParams();
    if (q.trim()) search.set('q', q.trim());
    if (category) search.set('category', category);
    if (geo) search.set('geo', geo);
    if (access) search.set('access_policy', access);
    const qs = search.toString();
    return qs ? `?${qs}` : '';
  }, [q, category, geo, access]);

  const { data: catalog, isLoading: catalogLoading } = useQuery<OffersResponse>({
    queryKey: ['partner', 'offers', 'marketplace', catalogParams],
    queryFn: () => api.get(`/partner/offers/marketplace${catalogParams}`),
  });
  const { data: mine, isLoading: mineLoading } = useQuery<OffersResponse>({
    queryKey: ['partner', 'offers', 'my'],
    queryFn: () => api.get('/partner/offers'),
  });

  const cancelRequest = useMutation({
    mutationFn: (offerId: string | number) => api.post(`/partner/offers/${offerId}/cancel-request`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      addToast('Заявка отменена', 'success');
    },
    onError: () => addToast('Не удалось отменить заявку', 'error'),
  });

  const joinOpen = useMutation({
    mutationFn: async (offer: OfferListItem) => {
      await api.post(`/partner/offers/${offer.id}/join`);
      return offer;
    },
    onSuccess: (offer) => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      addToast('Доступ предоставлен', 'success');
      setLinkOffer(offer);
    },
    onError: () => addToast('Не удалось получить доступ', 'error'),
  });

  const items = useMemo(() => {
    const catalogItems = catalog?.items || [];
    const myItems = mine?.items || [];
    if (tab === 'mine') {
      const rank: Record<string, number> = { ACTIVE: 0, PAUSED: 1, NOT_STARTED: 2 };
      return myItems
        .filter((item) => item.partner_status === 'approved')
        .sort(
          (a, b) =>
            (rank[a.promotion_status || 'NOT_STARTED'] ?? 2) -
            (rank[b.promotion_status || 'NOT_STARTED'] ?? 2),
        );
    }
    if (tab === 'pending') return myItems.filter((item) => item.partner_status === 'pending');
    if (tab === 'available') {
      return catalogItems.filter((item) => item.partner_status === 'approved' || item.access_policy === 'open');
    }
    return catalogItems;
  }, [catalog, mine, tab]);

  const isLoading = catalogLoading || mineLoading;
  const partnerName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || 'Партнёр';

  const openOfferDetails = (offerId: OfferListItem['id']) => {
    navigate(`/partner/offers/${offerId}`);
  };

  return (
    <div className="space-y-5">
      <h1 className="ui-page-title">Офферы</h1>
      <div className="flex flex-wrap gap-2">
        <input className="ui-input max-w-xs h-9" placeholder="Поиск..." value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="ui-input w-auto h-9" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Категория</option>
          {CATEGORIES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select className="ui-input w-auto h-9" value={geo} onChange={(e) => setGeo(e.target.value)}>
          <option value="">GEO</option>
          {GEO_OPTIONS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select className="ui-input w-auto h-9" value={access} onChange={(e) => setAccess(e.target.value)}>
          <option value="">Доступ</option>
          {ACCESS_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex gap-1 bg-muted rounded-md p-0.5 w-fit">
        {[
          { key: 'all', label: 'Все' },
          { key: 'available', label: 'Доступны' },
          { key: 'mine', label: 'Мои офферы' },
          { key: 'pending', label: 'Заявки' },
        ].map((item) => (
          <button key={item.key} type="button" className={tabClass(tab === item.key)} onClick={() => setTab(item.key as typeof tab)}>
            {item.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))}
        </div>
      ) : !items.length ? (
        <EmptyState title="Нет офферов" description="Измените фильтры или загляните позже." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((offer) => (
            <PartnerOfferCard
              key={offer.id}
              offer={offer}
              joined={offer.partner_status === 'approved'}
              pending={offer.partner_status === 'pending'}
              joinPending={joinOpen.isPending}
              onOpen={openOfferDetails}
              onGetLink={setLinkOffer}
              onOpenLinks={(item) => navigate(`/partner/links?offerId=${item.id}`)}
              onJoinOpen={(item) => joinOpen.mutate(item)}
              onRequestAccess={setRequestOffer}
              onCancelRequest={(offerId) => cancelRequest.mutate(offerId)}
            />
          ))}
        </div>
      )}

      {linkOffer && (
        <GetLinkModal lockedOffer={linkOffer} onClose={() => setLinkOffer(null)} />
      )}
      {requestOffer && (
        <RequestAccessModal offerId={requestOffer.id} partnerName={partnerName} onClose={() => setRequestOffer(null)} />
      )}
    </div>
  );
}
