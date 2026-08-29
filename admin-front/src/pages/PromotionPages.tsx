import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, errorMessage, qs } from '@/lib/api';
import { useQueryState } from '@/lib/url';
import { useAuth } from '@/lib/auth';
import { ADMIN_OPERATIONS } from '@/lib/permissions';
import { Button, CopyId, Kv, PageTitle, StatusBadge, formatDateTime, formatNumber, useToast } from '@/components/ui';
import { DataTable, OffsetPager, QueryState } from '@/components/Table';
import { EntityLink } from '@/components/EntityLink';
import { RqcidLink } from '@/components/RqcidLink';
import { ConfirmAction } from '@/components/ConfirmAction';
import { BusinessFilter } from '@/components/BusinessFilter';

type OffsetPage<T> = { items: T[]; page: number; pages: number };

function useAction(path: string) {
  const toast = useToast();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (reason: string) => api.post(path, { reason }),
    onSuccess: () => {
      toast.addToast('Действие выполнено', 'success');
      qc.invalidateQueries();
    },
    onError: (err) => toast.addToast(errorMessage(err), 'error'),
  });
}

export function SitesPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['sites', get('business_id'), get('status'), get('sdk'), page],
    queryFn: () =>
      api.get<OffsetPage<any>>(
        `/sites${qs({ business_id: get('business_id') || undefined, status: get('status'), sdk: get('sdk'), page })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Сайты" />
      <div className="flex flex-wrap gap-2 mb-3">
        <BusinessFilter value={get('business_id')} onChange={(business_id) => set({ business_id })} />
        <select className="ui-input h-8 w-36" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">Статус</option>
          <option value="active">Активен</option>
          <option value="disabled">Отключен</option>
        </select>
        <select className="ui-input h-8 w-44" value={get('sdk')} onChange={(e) => set({ sdk: e.target.value })}>
          <option value="">SDK</option>
          <option value="connected">Подключен</option>
          <option value="not_connected">Не подключен</option>
          <option value="no_activity">Нет активности</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'domain', header: 'Домен' },
            { key: 'business', header: 'Бизнес' },
            { key: 'sdk', header: 'Статус SDK' },
            { key: 'last', header: 'Последнее событие' },
            { key: 'events', header: 'События 24ч', align: 'right' },
            { key: 'status', header: 'Статус' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            domain: <EntityLink type="site" id={row.id}>{row.domain}</EntityLink>,
            business: <EntityLink type="business" id={row.business_id}>{row.business_name}</EntityLink>,
            sdk: <StatusBadge status={row.sdk_status} />,
            last: formatDateTime(row.last_event_at),
            events: row.events_24h == null ? '—' : formatNumber(row.events_24h),
            status: <StatusBadge status={row.status} />,
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(p) => set({ page: String(p) })} />
      </QueryState>
    </div>
  );
}

export function SiteDetailPage() {
  const { id } = useParams();
  const { has } = useAuth();
  const [action, setAction] = useState<'activate' | 'deactivate' | null>(null);
  const query = useQuery({ queryKey: ['site', id], queryFn: () => api.get<any>(`/sites/${id}`) });
  const mutation = useAction(`/sites/${id}/${action === 'activate' ? 'activate' : 'deactivate'}`);
  const data = query.data;
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle
            title={data.domain}
            actions={
              has(ADMIN_OPERATIONS) ? (
                data.status === 'active' ? (
                  <Button size="sm" variant="destructive" onClick={() => setAction('deactivate')}>Отключить</Button>
                ) : (
                  <Button size="sm" onClick={() => setAction('activate')}>Активировать</Button>
                )
              ) : null
            }
          />
          <div className="ui-card p-4">
            <Kv label="Бизнес"><EntityLink type="business" id={data.business_id}>{data.business_name}</EntityLink></Kv>
            <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
            <Kv label="SDK"><StatusBadge status={data.sdk_status} /></Kv>
            <Kv label="Первое событие">{formatDateTime(data.first_event_at)}</Kv>
            <Kv label="Последнее событие">{formatDateTime(data.last_event_at)}</Kv>
            <Kv label="События 24ч">{data.events_24h == null ? 'Недоступно' : formatNumber(data.events_24h)}</Kv>
          </div>
          <div className="ui-card p-4">
            <h3 className="ui-section-title mb-2">Разбивка событий</h3>
            <p className="text-sm text-muted-foreground">
              Хранилище clickstream не подключено. Счётчики page_view / click / scroll / custom не подставляются.
            </p>
          </div>
          {action && (
            <ConfirmAction
              title={action === 'deactivate' ? 'Отключить сайт?' : 'Активировать сайт?'}
              description="Статус сайта изменится через существующий SiteService."
              confirmLabel={action === 'deactivate' ? 'Отключить' : 'Активировать'}
              pending={mutation.isPending}
              onClose={() => setAction(null)}
              onConfirm={(reason) => mutation.mutate(reason, { onSuccess: () => setAction(null) })}
            />
          )}
        </div>
      )}
    </QueryState>
  );
}

export function OffersPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['offers', get('business_id'), get('status'), get('commission_type'), page],
    queryFn: () =>
      api.get<OffsetPage<any>>(
        `/offers${qs({
          business_id: get('business_id') || undefined,
          status: get('status'),
          commission_type: get('commission_type'),
          created_from: get('created_from') || undefined,
          page,
        })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Офферы" />
      <div className="flex flex-wrap gap-2 mb-3">
        <BusinessFilter value={get('business_id')} onChange={(business_id) => set({ business_id })} />
        <select className="ui-input h-8 w-36" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">Статус</option>
          <option value="active">Активен</option>
          <option value="paused">Приостановлен</option>
          <option value="draft">Черновик</option>
        </select>
        <select className="ui-input h-8 w-40" value={get('commission_type')} onChange={(e) => set({ commission_type: e.target.value })}>
          <option value="">Комиссия</option>
          <option value="percent">Процент</option>
          <option value="fixed">Фикс</option>
        </select>
        <input type="date" className="ui-input h-8 w-40" value={get('created_from')} onChange={(e) => set({ created_from: e.target.value })} />
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'offer', header: 'Оффер' },
            { key: 'business', header: 'Бизнес' },
            { key: 'status', header: 'Статус' },
            { key: 'commission', header: 'Комиссия' },
            { key: 'window', header: 'Окно атрибуции' },
            { key: 'partners', header: 'Партнёры', align: 'right' },
            { key: 'links', header: 'Ссылки', align: 'right' },
            { key: 'conversions', header: 'Конверсии 30д', align: 'right' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            offer: <EntityLink type="offer" id={row.id}>{row.name}</EntityLink>,
            business: <EntityLink type="business" id={row.business_id}>{row.business_name}</EntityLink>,
            status: <StatusBadge status={row.status} />,
            commission: row.commission?.type ? `${row.commission.type} ${row.commission.value}` : '—',
            window: `${row.attribution_window_days}d`,
            partners: formatNumber(row.partners),
            links: formatNumber(row.tracking_links),
            conversions: formatNumber(row.conversions_30d),
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(p) => set({ page: String(p) })} />
      </QueryState>
    </div>
  );
}

export function OfferDetailPage() {
  const { id } = useParams();
  const { has } = useAuth();
  const [action, setAction] = useState<'pause' | 'activate' | null>(null);
  const query = useQuery({ queryKey: ['offer', id], queryFn: () => api.get<any>(`/offers/${id}`) });
  const mutation = useAction(`/offers/${id}/${action === 'activate' ? 'activate' : 'pause'}`);
  const data = query.data;
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle
            title={data.name}
            actions={
              has(ADMIN_OPERATIONS) ? (
                data.status === 'ACTIVE' ? (
                  <Button size="sm" variant="destructive" onClick={() => setAction('pause')}>Приостановить</Button>
                ) : (
                  <Button size="sm" onClick={() => setAction('activate')}>Активировать</Button>
                )
              ) : null
            }
          />
          <div className="grid grid-cols-2 gap-4">
            <div className="ui-card p-4">
              <h3 className="ui-section-title mb-2">Основная информация</h3>
              <Kv label="ID"><CopyId value={data.id} /></Kv>
              <Kv label="Бизнес"><EntityLink type="business" id={data.business_id}>{data.business_name}</EntityLink></Kv>
              <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
              <Kv label="Категория">{data.category}</Kv>
              <Kv label="Гео">{Array.isArray(data.geo) ? data.geo.join(', ') : data.geo}</Kv>
            </div>
            <div className="ui-card p-4">
              <h3 className="ui-section-title mb-2">Комиссия / Атрибуция</h3>
              <Kv label="Тип">{data.commission?.type}</Kv>
              <Kv label="Значение">{data.commission?.value} {data.commission?.currency}</Kv>
              <Kv label="Окно">{data.attribution_window_days} дн.</Kv>
            </div>
          </div>
          <div className="ui-card p-4">
            <h3 className="ui-section-title mb-2">Правила</h3>
            <Kv label="Разрешено">{(data.allowed_traffic || []).join(', ') || '—'}</Kv>
            <Kv label="Запрещено">{(data.forbidden_traffic || []).join(', ') || '—'}</Kv>
          </div>
          <div className="ui-card p-4">
            <h3 className="ui-section-title mb-2">Партнёры</h3>
            {(data.partners || []).map((row: any) => (
              <div key={row.id} className="flex justify-between text-sm py-1">
                <EntityLink type="partner" id={row.id}>Партнёр #{row.id}</EntityLink>
                <StatusBadge status={row.status} />
              </div>
            ))}
          </div>
          <div className="ui-card p-4">
            <h3 className="ui-section-title mb-2">Ссылки</h3>
            {(data.tracking_links || []).map((row: any) => (
              <div key={row.id} className="flex justify-between text-sm py-1">
                <EntityLink type="tracking_link" id={row.id}>{row.short_code}</EntityLink>
                <StatusBadge status={row.status} />
              </div>
            ))}
          </div>
          <div className="ui-card p-4">
            <h3 className="ui-section-title mb-2">Материалы</h3>
            {(data.creatives || []).length === 0 && <p className="text-sm text-muted-foreground">Нет материалов</p>}
            {(data.creatives || []).map((row: any) => (
              <div key={row.id} className="text-sm py-1">{row.title || row.type} · {row.status}</div>
            ))}
          </div>
          <div className="ui-card p-4">
            <h3 className="ui-section-title mb-2">Конверсии</h3>
            {(data.conversions || []).map((row: any) => (
              <div key={row.id} className="flex justify-between text-sm py-1">
                <EntityLink type="conversion" id={row.id}>#{row.id}</EntityLink>
                <RqcidLink rqcid={row.rqcid} />
              </div>
            ))}
          </div>
          {action && (
            <ConfirmAction
              title={action === 'pause' ? 'Приостановить оффер?' : 'Активировать оффер?'}
              description="Статус оффера изменится через существующий доменный сервис."
              confirmLabel={action === 'pause' ? 'Приостановить' : 'Активировать'}
              pending={mutation.isPending}
              onClose={() => setAction(null)}
              onConfirm={(reason) => mutation.mutate(reason, { onSuccess: () => setAction(null) })}
            />
          )}
        </div>
      )}
    </QueryState>
  );
}

export function TrackingLinksPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['links', get('q'), get('status'), get('business_id'), page],
    queryFn: () =>
      api.get<OffsetPage<any>>(
        `/tracking-links${qs({ q: get('q'), status: get('status'), business_id: get('business_id') || undefined, page })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Ссылки" />
      <div className="flex flex-wrap gap-2 mb-3">
        <BusinessFilter value={get('business_id')} onChange={(business_id) => set({ business_id })} />
        <input className="ui-input h-8 w-48" placeholder="shortCode" defaultValue={get('q')} onBlur={(e) => set({ q: e.target.value })} />
        <select className="ui-input h-8 w-36" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">Статус</option>
          <option value="ACTIVE">Активна</option>
          <option value="DISABLED">Отключена</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'code', header: 'shortCode' },
            { key: 'offer', header: 'Оффер' },
            { key: 'partner', header: 'Партнёр' },
            { key: 'campaign', header: 'Кампания' },
            { key: 'destination', header: 'Целевая страница' },
            { key: 'status', header: 'Статус' },
            { key: 'clicks', header: 'Клики', align: 'right' },
            { key: 'conversions', header: 'Конверсии', align: 'right' },
            { key: 'last', header: 'Последний клик' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            code: <EntityLink type="tracking_link" id={row.id}>{row.short_code}</EntityLink>,
            offer: <EntityLink type="offer" id={row.offer_id}>{row.offer_name}</EntityLink>,
            partner: <EntityLink type="partner" id={row.partner_id}>{row.partner_name}</EntityLink>,
            campaign: row.campaign_name || '—',
            destination: <span className="truncate block max-w-[220px]">{row.destination_url}</span>,
            status: <StatusBadge status={row.status} />,
            clicks: formatNumber(row.clicks),
            conversions: formatNumber(row.conversions),
            last: formatDateTime(row.last_click_at),
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(p) => set({ page: String(p) })} />
      </QueryState>
    </div>
  );
}

export function TrackingLinkDetailPage() {
  const { id } = useParams();
  const { has } = useAuth();
  const [action, setAction] = useState<'pause' | 'activate' | 'qr' | null>(null);
  const query = useQuery({ queryKey: ['link', id], queryFn: () => api.get<any>(`/tracking-links/${id}`) });
  const mutation = useAction(
    `/tracking-links/${id}/${action === 'activate' ? 'activate' : action === 'qr' ? 'regenerate-qr' : 'pause'}`,
  );
  const data = query.data;
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle
            title={data.short_code}
            actions={
              has(ADMIN_OPERATIONS) ? (
                <>
                  {data.status === 'active' ? (
                    <Button size="sm" variant="destructive" onClick={() => setAction('pause')}>Приостановить</Button>
                  ) : (
                    <Button size="sm" onClick={() => setAction('activate')}>Активировать</Button>
                  )}
                  <Button size="sm" variant="outline" onClick={() => setAction('qr')}>Пересоздать QR</Button>
                </>
              ) : null
            }
          />
          <div className="grid grid-cols-[1fr_240px] gap-4">
            <div className="ui-card p-4">
              <Kv label="Публичный URL"><a className="text-primary" href={data.public_url} target="_blank" rel="noreferrer">{data.public_url}</a></Kv>
              <Kv label="Бизнес"><EntityLink type="business" id={data.business_id}>{data.business_name}</EntityLink></Kv>
              <Kv label="Партнёр"><EntityLink type="partner" id={data.partner_id}>{data.partner_name}</EntityLink></Kv>
              <Kv label="Оффер"><EntityLink type="offer" id={data.offer_id}>{data.offer_name}</EntityLink></Kv>
              <Kv label="Кампания">{data.campaign_name || '—'}</Kv>
              <Kv label="Целевая страница">{data.destination_url}</Kv>
              <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
              <Kv label="Создана">{formatDateTime(data.created_at)}</Kv>
              <Kv label="Последний клик">{formatDateTime(data.last_click_at)}</Kv>
              <Kv label="Клики всего">{formatNumber(data.clicks_total)}</Kv>
              <Kv label="Конверсии всего">{formatNumber(data.conversions_total)}</Kv>
            </div>
            <div className="ui-card p-4">
              <h3 className="ui-section-title mb-2">QR-код</h3>
              <img alt="QR" className="w-full border rounded-md" src={`/api/admin/v1/tracking-links/${id}/qr`} />
            </div>
          </div>
          {action && (
            <ConfirmAction
              title={action === 'qr' ? 'Пересоздать QR?' : action === 'pause' ? 'Отключить ссылку?' : 'Активировать ссылку?'}
              description="QR остаётся производным артефактом этой ссылки."
              confirmLabel={action === 'qr' ? 'Пересоздать' : action === 'pause' ? 'Отключить' : 'Активировать'}
              pending={mutation.isPending}
              onClose={() => setAction(null)}
              onConfirm={(reason) => mutation.mutate(reason, { onSuccess: () => setAction(null) })}
            />
          )}
        </div>
      )}
    </QueryState>
  );
}
