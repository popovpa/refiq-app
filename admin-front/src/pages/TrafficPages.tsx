import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, qs } from '@/lib/api';
import { useQueryState } from '@/lib/url';
import { CopyId, Kv, PageTitle, StatusBadge, formatDateTime, formatNumber } from '@/components/ui';
import { CursorPager, DataTable, QueryState } from '@/components/Table';
import { EntityLink } from '@/components/EntityLink';
import { RqcidLink } from '@/components/RqcidLink';
import { BusinessFilter } from '@/components/BusinessFilter';

type CursorPage<T> = { items: T[]; next_cursor: string | null; has_more: boolean };

export function ClicksPage() {
  const { get, set } = useQueryState();
  const query = useQuery({
    queryKey: ['clicks', get('cursor'), get('rqcid'), get('business_id')],
    queryFn: () =>
      api.get<CursorPage<any>>(
        `/clicks${qs({
          cursor: get('cursor') || undefined,
          rqcid: get('rqcid') || undefined,
          business_id: get('business_id') || undefined,
        })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Клики" />
      <div className="flex flex-wrap gap-2 mb-3">
        <BusinessFilter value={get('business_id')} onChange={(business_id) => set({ business_id })} />
        <input className="ui-input h-8 w-48" placeholder="rqcid" defaultValue={get('rqcid')} onBlur={(e) => set({ rqcid: e.target.value })} />
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'time', header: 'Время' },
            { key: 'rqcid', header: 'rqcid' },
            { key: 'code', header: 'shortCode' },
            { key: 'offer', header: 'Оффер' },
            { key: 'partner', header: 'Партнёр' },
            { key: 'site', header: 'Сайт' },
            { key: 'source', header: 'Источник' },
            { key: 'country', header: 'Страна' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            time: formatDateTime(row.created_at),
            rqcid: <RqcidLink rqcid={row.rqcid} />,
            code: <EntityLink type="tracking_link" id={row.tracking_link_id}>{row.short_code}</EntityLink>,
            offer: <EntityLink type="offer" id={row.offer_id}>{row.offer_name}</EntityLink>,
            partner: <EntityLink type="partner" id={row.partner_id}>{row.partner_name}</EntityLink>,
            site: row.site_id ? <EntityLink type="site" id={row.site_id}>{row.site_domain}</EntityLink> : '—',
            source: row.source || '—',
            country: row.country || '—',
          }))}
        />
        <CursorPager hasMore={Boolean(query.data?.has_more)} onMore={() => set({ cursor: query.data?.next_cursor || undefined })} />
      </QueryState>
    </div>
  );
}

export function ClickDetailPage() {
  const { rqcid } = useParams();
  const [openTech, setOpenTech] = useState(false);
  const query = useQuery({ queryKey: ['click', rqcid], queryFn: () => api.get<any>(`/clicks/${rqcid}`) });
  const data = query.data;
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle title={data.rqcid} actions={<Link className="text-sm text-primary" to={`/trace/${data.rqcid}`}>Открыть трассировку</Link>} />
          <div className="ui-card p-4">
            <Kv label="rqcid"><RqcidLink rqcid={data.rqcid} /></Kv>
            <Kv label="Создан">{formatDateTime(data.created_at)}</Kv>
            <Kv label="Ссылка"><EntityLink type="tracking_link" id={data.tracking_link_id}>{data.short_code}</EntityLink></Kv>
            <Kv label="Оффер"><EntityLink type="offer" id={data.offer_id}>{data.offer_name}</EntityLink></Kv>
            <Kv label="Партнёр"><EntityLink type="partner" id={data.partner_id}>{data.partner_name}</EntityLink></Kv>
            <Kv label="Бизнес"><EntityLink type="business" id={data.business_id}>{data.business_name}</EntityLink></Kv>
            <Kv label="Целевая страница">{data.destination_url}</Kv>
            <Kv label="Referrer">{data.referrer || '—'}</Kv>
            <Kv label="Источник">{data.source || '—'}</Kv>
            <Kv label="Страна">{data.country || '—'}</Kv>
            <Kv label="Устройство">{data.device || '—'}</Kv>
          </div>
          <button type="button" className="text-sm text-primary" onClick={() => setOpenTech((v) => !v)}>
            Технические детали
          </button>
          {openTech && (
            <div className="ui-card p-4 text-xs font-mono">
              <Kv label="IP клиента">{data.technical?.client_ip || '—'}</Kv>
              <Kv label="User agent">{data.technical?.user_agent || '—'}</Kv>
            </div>
          )}
        </div>
      )}
    </QueryState>
  );
}

export function ConversionsPage() {
  const { get, set } = useQueryState();
  const query = useQuery({
    queryKey: ['conversions', get('cursor'), get('business_id'), get('status')],
    queryFn: () =>
      api.get<CursorPage<any>>(
        `/conversions${qs({ cursor: get('cursor') || undefined, business_id: get('business_id') || undefined, status: get('status') || undefined })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Конверсии" />
      <div className="flex flex-wrap gap-2 mb-3">
        <BusinessFilter value={get('business_id')} onChange={(business_id) => set({ business_id })} />
        <select className="ui-input h-8 w-36" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">Статус</option>
          <option value="approved">Одобрена</option>
          <option value="pending">Ожидает</option>
          <option value="rejected">Отклонена</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'time', header: 'Время' },
            { key: 'conversion', header: 'Конверсия' },
            { key: 'rqcid', header: 'rqcid' },
            { key: 'business', header: 'Бизнес' },
            { key: 'offer', header: 'Оффер' },
            { key: 'partner', header: 'Партнёр' },
            { key: 'value', header: 'Сумма', align: 'right' },
            { key: 'commission', header: 'Комиссия', align: 'right' },
            { key: 'status', header: 'Статус' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            time: formatDateTime(row.created_at),
            conversion: <EntityLink type="conversion" id={row.id}>#{row.id}</EntityLink>,
            rqcid: <RqcidLink rqcid={row.rqcid} />,
            business: <EntityLink type="business" id={row.business_id}>{row.business_name}</EntityLink>,
            offer: <EntityLink type="offer" id={row.offer_id}>{row.offer_name}</EntityLink>,
            partner: <EntityLink type="partner" id={row.partner_id}>{row.partner_name}</EntityLink>,
            value: formatNumber(row.value),
            commission: formatNumber(row.commission),
            status: <StatusBadge status={row.status} />,
          }))}
        />
        <CursorPager hasMore={Boolean(query.data?.has_more)} onMore={() => set({ cursor: query.data?.next_cursor || undefined })} />
      </QueryState>
    </div>
  );
}

export function ConversionDetailPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ['conversion', id], queryFn: () => api.get<any>(`/conversions/${id}`) });
  const data = query.data;
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle
            title={`Конверсия #${data.id}`}
            actions={
              data.rqcid ? (
                <Link className="h-8 px-3 rounded-md bg-primary text-primary-foreground text-sm inline-flex items-center" to={`/trace/${data.rqcid}`}>
                  Трассировка rqcid
                </Link>
              ) : null
            }
          />
          <div className="ui-card p-4">
            <Kv label="ID конверсии"><CopyId value={data.id} /></Kv>
            <Kv label="rqcid"><RqcidLink rqcid={data.rqcid} /></Kv>
            <Kv label="Бизнес"><EntityLink type="business" id={data.business_id}>{data.business_name}</EntityLink></Kv>
            <Kv label="Оффер"><EntityLink type="offer" id={data.offer_id}>{data.offer_name}</EntityLink></Kv>
            <Kv label="Партнёр"><EntityLink type="partner" id={data.partner_id}>{data.partner_name}</EntityLink></Kv>
            <Kv label="Заказ / External ID">{data.external_id || '—'}</Kv>
            <Kv label="Сумма заказа">{formatNumber(data.amount)} {data.currency}</Kv>
            <Kv label="Комиссия">
              {data.commission_id ? (
                <EntityLink type="commission" id={data.commission_id}>{formatNumber(data.commission_amount)}</EntityLink>
              ) : (
                formatNumber(data.commission_amount)
              )}
            </Kv>
            <Kv label="Атрибуция">{data.attribution_result}</Kv>
            <Kv label="Postback">{data.postback_id ? `${data.postback_id} · ${data.postback_result}` : '—'}</Kv>
            <Kv label="Создан">{formatDateTime(data.created_at)}</Kv>
            <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
            <Kv label="Статус выплаты">
              {data.payout_id ? <EntityLink type="payout" id={data.payout_id}>{data.payout_status || data.payout_id}</EntityLink> : '—'}
            </Kv>
          </div>
        </div>
      )}
    </QueryState>
  );
}

export function PostbacksPage() {
  const { get, set } = useQueryState();
  const query = useQuery({
    queryKey: ['postbacks', get('cursor'), get('result'), get('business_id')],
    queryFn: () =>
      api.get<CursorPage<any>>(
        `/postbacks${qs({
          cursor: get('cursor') || undefined,
          result: get('result') || undefined,
          business_id: get('business_id') || undefined,
        })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Postback" />
      <div className="flex flex-wrap gap-2 mb-3">
        <BusinessFilter value={get('business_id')} onChange={(business_id) => set({ business_id })} />
        <select className="ui-input h-8 w-40" value={get('result')} onChange={(e) => set({ result: e.target.value })}>
          <option value="">Результат</option>
          <option value="ACCEPTED">Принят</option>
          <option value="REJECTED">Отклонён</option>
          <option value="DUPLICATE">Дубликат</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'time', header: 'Время' },
            { key: 'business', header: 'Бизнес' },
            { key: 'rqcid', header: 'rqcid' },
            { key: 'result', header: 'Результат' },
            { key: 'reason', header: 'Причина' },
            { key: 'conversion', header: 'Конверсия' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            time: formatDateTime(row.received_at),
            business: row.business_id ? <EntityLink type="business" id={row.business_id}>{row.business_name}</EntityLink> : '—',
            rqcid: <RqcidLink rqcid={row.rqcid} />,
            result: <StatusBadge status={row.result} />,
            reason: row.reason_code || '—',
            conversion: row.conversion_id ? <EntityLink type="conversion" id={row.conversion_id}>#{row.conversion_id}</EntityLink> : '—',
          }))}
        />
        <CursorPager hasMore={Boolean(query.data?.has_more)} onMore={() => set({ cursor: query.data?.next_cursor || undefined })} />
      </QueryState>
    </div>
  );
}
