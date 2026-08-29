import { useState, type InputHTMLAttributes } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
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
import { COLUMN_LABELS, TAB_LABELS, aggregateLabel } from '@/lib/labels';

type OffsetPage<T> = { items: T[]; total: number; page: number; pages: number };
type CursorPage<T> = { items: T[]; next_cursor: string | null; has_more: boolean };

function FilterInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className="ui-input h-8 w-48" {...props} />;
}

function FilterSelect({
  value,
  onChange,
  options,
  allLabel = 'Все',
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<string | { value: string; label: string }>;
  allLabel?: string;
}) {
  return (
    <select className="ui-input h-8 w-40" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allLabel}</option>
      {options.map((item) => {
        const opt = typeof item === 'string' ? { value: item, label: item } : item;
        return (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        );
      })}
    </select>
  );
}

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

export function BusinessesPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['businesses', get('q'), get('status'), get('has_sites'), get('has_offers'), page],
    queryFn: () =>
      api.get<OffsetPage<Record<string, never>>>(
        `/businesses${qs({
          q: get('q'),
          status: get('status'),
          has_connected_sites: get('has_sites') || undefined,
          has_active_offers: get('has_offers') || undefined,
          created_from: get('created_from') || undefined,
          created_to: get('created_to') || undefined,
          page,
        })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Бизнесы" />
      <div className="flex flex-wrap gap-2 mb-3">
        <FilterInput placeholder="Название, ID, email владельца" defaultValue={get('q')} onBlur={(e) => set({ q: e.target.value })} />
        <FilterSelect value={get('status')} onChange={(status) => set({ status })} options={[
          { value: 'active', label: 'Активен' },
          { value: 'suspended', label: 'Приостановлен' },
        ]} />
        <FilterSelect value={get('has_sites')} onChange={(has_sites) => set({ has_sites })} options={['true']} allLabel="Сайты" />
        <FilterSelect value={get('has_offers')} onChange={(has_offers) => set({ has_offers })} options={['true']} allLabel="Активные офферы" />
        <input type="date" className="ui-input h-8 w-40" value={get('created_from')} onChange={(e) => set({ created_from: e.target.value })} />
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'name', header: 'Бизнес' },
            { key: 'owner', header: 'Владелец' },
            { key: 'sites', header: 'Сайты', align: 'right' },
            { key: 'offers', header: 'Офферы', align: 'right' },
            { key: 'partners', header: 'Партнёры', align: 'right' },
            { key: 'conversions', header: 'Конверсии 30д', align: 'right' },
            { key: 'status', header: 'Статус' },
            { key: 'activity', header: 'Последняя активность' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            name: <EntityLink type="business" id={row.id}>{row.name}</EntityLink>,
            owner: row.owner_email,
            sites: formatNumber(row.sites),
            offers: formatNumber(row.offers),
            partners: formatNumber(row.partners),
            conversions: formatNumber(row.conversions_30d),
            status: <StatusBadge status={row.status} />,
            activity: formatDateTime(row.last_activity_at),
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(next) => set({ page: String(next) })} />
      </QueryState>
    </div>
  );
}

export function BusinessDetailPage() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') || 'overview';
  const { has } = useAuth();
  const [action, setAction] = useState<'suspend' | 'activate' | null>(null);
  const query = useQuery({ queryKey: ['business', id], queryFn: () => api.get<any>(`/businesses/${id}`) });
  const data = query.data;
  const mutation = useAction(`/businesses/${id}/${action === 'activate' ? 'activate' : 'suspend'}`);
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle
            title={data.name}
            actions={
              has(ADMIN_OPERATIONS) ? (
                data.status === 'suspended' ? (
                  <Button size="sm" onClick={() => setAction('activate')}>Возобновить</Button>
                ) : (
                  <Button size="sm" variant="destructive" onClick={() => setAction('suspend')}>Приостановить</Button>
                )
              ) : null
            }
          />
          <div className="ui-card p-4">
            <Kv label="ID"><CopyId value={data.id} /></Kv>
            <Kv label="Владелец">{data.owner_email}</Kv>
            <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
            <Kv label="Создан">{formatDateTime(data.created_at)}</Kv>
            <Kv label="Обновлён">{formatDateTime(data.updated_at)}</Kv>
          </div>
          <div className="flex gap-2 text-sm">
            {(['overview', 'sites', 'offers', 'partners', 'conversions', 'finance'] as const).map((item) => (
              <button
                key={item}
                className={`px-3 py-1.5 rounded-md ${tab === item ? 'bg-accent text-primary' : 'text-muted-foreground'}`}
                onClick={() => setParams({ tab: item })}
              >
                {TAB_LABELS[item]}
              </button>
            ))}
          </div>
          {tab === 'overview' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="ui-card p-4">
                {Object.entries(data.aggregates || {}).map(([key, value]) => (
                  <Kv key={key} label={aggregateLabel(key)}>{formatNumber(value as number)}</Kv>
                ))}
              </div>
              <div className="space-y-3">
                <div className="ui-card p-4">
                  <h3 className="ui-section-title mb-2">Недавние конверсии</h3>
                  {(data.recent_conversions || []).map((item: any) => (
                    <div key={item.id} className="flex justify-between text-sm py-1">
                      <EntityLink type="conversion" id={item.id}>#{item.id}</EntityLink>
                      <RqcidLink rqcid={item.rqcid} />
                    </div>
                  ))}
                </div>
                <div className="ui-card p-4">
                  <h3 className="ui-section-title mb-2">Недавние ссылки</h3>
                  {(data.recent_tracking_links || []).map((item: any) => (
                    <div key={item.id} className="flex justify-between text-sm py-1">
                      <EntityLink type="tracking_link" id={item.id}>{item.short_code}</EntityLink>
                      <StatusBadge status={item.status} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          {tab === 'sites' && (
            <RelatedTable
              rows={data.sites}
              columns={['domain', 'status']}
              href={(row) => `/sites/${row.id}`}
            />
          )}
          {tab === 'offers' && (
            <RelatedTable rows={data.offers} columns={['name', 'status']} href={(row) => `/offers/${row.id}`} />
          )}
          {tab === 'partners' && (
            <RelatedTable rows={data.partners} columns={['name', 'status']} href={(row) => `/partners/${row.id}`} />
          )}
          {tab === 'conversions' && <Link className="text-primary text-sm" to={`/conversions?business_id=${id}`}>Открыть конверсии</Link>}
          {tab === 'finance' && <Link className="text-primary text-sm" to={`/commissions?business_id=${id}`}>Открыть комиссии</Link>}
          {action && (
            <ConfirmAction
              title={action === 'suspend' ? 'Приостановить бизнес?' : 'Возобновить бизнес?'}
              description="Статус бизнеса изменится через существующий доменный сервис."
              confirmLabel={action === 'suspend' ? 'Приостановить' : 'Возобновить'}
              destructive={action === 'suspend'}
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

function RelatedTable({
  rows,
  columns,
  href,
}: {
  rows: any[];
  columns: string[];
  href: (row: any) => string;
}) {
  return (
    <DataTable
      columns={columns.map((key) => ({ key, header: COLUMN_LABELS[key] || key }))}
      rows={(rows || []).map((row) => ({
        id: row.id,
        ...Object.fromEntries(
          columns.map((key) => [
            key,
            key === columns[0] ? <Link to={href(row)} className="text-primary hover:underline">{row[key]}</Link> : key === 'status' ? <StatusBadge status={row[key]} /> : row[key],
          ]),
        ),
      }))}
    />
  );
}

export function PartnersPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['partners', get('q'), get('status'), page],
    queryFn: () => api.get<OffsetPage<any>>(`/partners${qs({ q: get('q'), status: get('status'), page })}`),
  });
  return (
    <div>
      <PageTitle title="Партнёры" />
      <div className="flex gap-2 mb-3">
        <FilterInput placeholder="Имя или email" defaultValue={get('q')} onBlur={(e) => set({ q: e.target.value })} />
        <FilterSelect value={get('status')} onChange={(status) => set({ status })} options={[
          { value: 'active', label: 'Активен' },
          { value: 'suspended', label: 'Приостановлен' },
        ]} />
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'name', header: 'Партнёр' },
            { key: 'email', header: 'Email' },
            { key: 'offers', header: 'Офферы', align: 'right' },
            { key: 'links', header: 'Ссылки', align: 'right' },
            { key: 'clicks', header: 'Клики 30д', align: 'right' },
            { key: 'conversions', header: 'Конверсии 30д', align: 'right' },
            { key: 'earnings', header: 'Заработано', align: 'right' },
            { key: 'status', header: 'Статус' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            name: <EntityLink type="partner" id={row.id}>{row.name}</EntityLink>,
            email: row.email,
            offers: formatNumber(row.offers),
            links: formatNumber(row.tracking_links),
            clicks: formatNumber(row.clicks_30d),
            conversions: formatNumber(row.conversions_30d),
            earnings: formatNumber(row.earnings),
            status: <StatusBadge status={row.status} />,
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(next) => set({ page: String(next) })} />
      </QueryState>
    </div>
  );
}

export function PartnerDetailPage() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') || 'profile';
  const { has } = useAuth();
  const [action, setAction] = useState<'block' | 'unblock' | null>(null);
  const query = useQuery({ queryKey: ['partner', id], queryFn: () => api.get<any>(`/partners/${id}`) });
  const clicks = useQuery({
    queryKey: ['partner-clicks', id],
    queryFn: () => api.get<CursorPage<any>>(`/clicks${qs({ partner_id: id, limit: 20 })}`),
    enabled: tab === 'clicks',
  });
  const commissions = useQuery({
    queryKey: ['partner-commissions', id],
    queryFn: () => api.get<OffsetPage<any>>(`/commissions${qs({ partner_id: id })}`),
    enabled: tab === 'commissions' && has('ADMIN_FINANCE'),
  });
  const payouts = useQuery({
    queryKey: ['partner-payouts', id],
    queryFn: () => api.get<OffsetPage<any>>(`/payouts${qs({ partner_id: id })}`),
    enabled: tab === 'payouts' && has('ADMIN_FINANCE'),
  });
  const mutation = useAction(`/partners/${id}/${action === 'unblock' ? 'unblock' : 'block'}`);
  const data = query.data;
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle
            title={data.name || `Партнёр #${data.id}`}
            actions={
              has(ADMIN_OPERATIONS) ? (
                data.status === 'suspended' ? (
                  <Button size="sm" onClick={() => setAction('unblock')}>Разблокировать</Button>
                ) : (
                  <Button size="sm" variant="destructive" onClick={() => setAction('block')}>Заблокировать</Button>
                )
              ) : null
            }
          />
          <div className="flex gap-2 text-sm">
            {(['profile', 'offers', 'links', 'clicks', 'conversions', ...(has('ADMIN_FINANCE') ? ['commissions', 'payouts'] : [])] as string[]).map((item) => (
              <button key={item} className={`px-3 py-1.5 rounded-md ${tab === item ? 'bg-accent text-primary' : 'text-muted-foreground'}`} onClick={() => setParams({ tab: item })}>
                {TAB_LABELS[item]}
              </button>
            ))}
          </div>
          {tab === 'profile' && (
            <div className="ui-card p-4">
              <Kv label="ID"><CopyId value={data.id} /></Kv>
              <Kv label="Email">{data.email}</Kv>
              <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
              <Kv label="Создан">{formatDateTime(data.created_at)}</Kv>
            </div>
          )}
          {tab === 'offers' && <RelatedTable rows={data.offers} columns={['name', 'status']} href={(row) => `/offers/${row.id}`} />}
          {tab === 'links' && (
            <DataTable
              columns={[{ key: 'code', header: 'shortCode' }, { key: 'status', header: 'Статус' }]}
              rows={(data.tracking_links || []).map((row: any) => ({
                id: row.id,
                code: <EntityLink type="tracking_link" id={row.id}>{row.short_code}</EntityLink>,
                status: <StatusBadge status={row.status} />,
              }))}
            />
          )}
          {tab === 'clicks' && (
            <DataTable
              columns={[{ key: 'time', header: 'Время' }, { key: 'rqcid', header: 'rqcid' }, { key: 'code', header: 'shortCode' }]}
              rows={(clicks.data?.items || []).map((row: any) => ({
                id: row.id,
                time: formatDateTime(row.created_at),
                rqcid: <RqcidLink rqcid={row.rqcid} />,
                code: <EntityLink type="tracking_link" id={row.tracking_link_id}>{row.short_code}</EntityLink>,
              }))}
            />
          )}
          {tab === 'conversions' && (
            <DataTable
              columns={[{ key: 'id', header: 'Конверсия' }, { key: 'rqcid', header: 'rqcid' }, { key: 'status', header: 'Статус' }]}
              rows={(data.conversions || []).map((row: any) => ({
                id: <EntityLink type="conversion" id={row.id}>#{row.id}</EntityLink>,
                rqcid: <RqcidLink rqcid={row.rqcid} />,
                status: <StatusBadge status={row.status} />,
              }))}
            />
          )}
          {tab === 'commissions' && (
            <QueryState loading={commissions.isLoading} error={commissions.error} empty={!commissions.data?.items.length}>
              <DataTable
                columns={[{ key: 'id', header: 'Комиссия' }, { key: 'amount', header: 'Сумма', align: 'right' }, { key: 'status', header: 'Статус' }]}
                rows={(commissions.data?.items || []).map((row: any) => ({
                  id: <EntityLink type="commission" id={row.id}>#{row.id}</EntityLink>,
                  amount: formatNumber(row.amount),
                  status: <StatusBadge status={row.status} />,
                }))}
              />
            </QueryState>
          )}
          {tab === 'payouts' && (
            <QueryState loading={payouts.isLoading} error={payouts.error} empty={!payouts.data?.items.length}>
              <DataTable
                columns={[{ key: 'id', header: 'Выплата' }, { key: 'amount', header: 'Сумма', align: 'right' }, { key: 'status', header: 'Статус' }]}
                rows={(payouts.data?.items || []).map((row: any) => ({
                  id: <EntityLink type="payout" id={row.id}>#{row.id}</EntityLink>,
                  amount: formatNumber(row.amount),
                  status: <StatusBadge status={row.status} />,
                }))}
              />
            </QueryState>
          )}
          {action && (
            <ConfirmAction
              title={action === 'block' ? 'Заблокировать партнёра?' : 'Разблокировать партнёра?'}
              description="Статус изменится по существующим правилам домена партнёра."
              confirmLabel={action === 'block' ? 'Заблокировать' : 'Разблокировать'}
              destructive={action === 'block'}
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
