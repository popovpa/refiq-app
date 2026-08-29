import type { ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, qs } from '@/lib/api';
import { useQueryState } from '@/lib/url';
import { useAuth } from '@/lib/auth';
import { ADMIN_FINANCE } from '@/lib/permissions';
import { CopyId, EmptyState, Kv, PageTitle, StatusBadge, formatDateTime, formatNumber } from '@/components/ui';
import { DataTable, OffsetPager, QueryState } from '@/components/Table';
import { EntityLink } from '@/components/EntityLink';
import { RqcidLink } from '@/components/RqcidLink';

type OffsetPage<T> = { items: T[]; page: number; pages: number };

function FinanceGate({ children }: { children: ReactNode }) {
  const { has } = useAuth();
  if (!has(ADMIN_FINANCE)) {
    return <EmptyState title="Недостаточно прав" description="Для этого раздела нужна роль ADMIN_FINANCE." />;
  }
  return <>{children}</>;
}

export function CommissionsPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['commissions', get('status'), get('partner_id'), get('business_id'), page],
    queryFn: () =>
      api.get<OffsetPage<any>>(
        `/commissions${qs({
          status: get('status') || undefined,
          partner_id: get('partner_id') || undefined,
          business_id: get('business_id') || undefined,
          page,
        })}`,
      ),
  });
  return (
    <FinanceGate>
      <PageTitle title="Комиссии" />
      <div className="flex gap-2 mb-3">
        <select className="ui-input h-8 w-40" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">Статус</option>
          <option value="pending">Ожидает</option>
          <option value="approved">Одобрена</option>
          <option value="paid">Выплачено</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'partner', header: 'Партнёр' },
            { key: 'conversion', header: 'Конверсия' },
            { key: 'offer', header: 'Оффер' },
            { key: 'amount', header: 'Сумма', align: 'right' },
            { key: 'status', header: 'Статус' },
            { key: 'payout', header: 'Выплата' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            partner: <EntityLink type="partner" id={row.partner_id}>{row.partner_name}</EntityLink>,
            conversion: <EntityLink type="conversion" id={row.conversion_id}>#{row.conversion_id}</EntityLink>,
            offer: row.offer_name,
            amount: `${formatNumber(row.amount)} ${row.currency || ''}`.trim(),
            status: <StatusBadge status={row.status} />,
            payout: row.payout_id ? <EntityLink type="payout" id={row.payout_id}>#{row.payout_id}</EntityLink> : '—',
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(p) => set({ page: String(p) })} />
      </QueryState>
    </FinanceGate>
  );
}

export function CommissionDetailPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ['commission', id], queryFn: () => api.get<any>(`/commissions/${id}`) });
  const data = query.data;
  return (
    <FinanceGate>
      <QueryState loading={query.isLoading} error={query.error}>
        {data && (
          <div className="ui-card p-4">
            <PageTitle title={`Комиссия #${data.id}`} />
            <Kv label="Партнёр"><EntityLink type="partner" id={data.partner_id}>{data.partner_name}</EntityLink></Kv>
            <Kv label="Конверсия"><EntityLink type="conversion" id={data.conversion_id}>#{data.conversion_id}</EntityLink></Kv>
            <Kv label="Оффер"><EntityLink type="offer" id={data.offer_id}>{data.offer_name}</EntityLink></Kv>
            <Kv label="rqcid"><RqcidLink rqcid={data.rqcid} /></Kv>
            <Kv label="Сумма">{formatNumber(data.amount)} {data.currency}</Kv>
            <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
            <Kv label="Выплата">{data.payout_id ? <EntityLink type="payout" id={data.payout_id}>#{data.payout_id}</EntityLink> : '—'}</Kv>
          </div>
        )}
      </QueryState>
    </FinanceGate>
  );
}

export function PayoutsPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['payouts', get('status'), get('partner_id'), page],
    queryFn: () =>
      api.get<OffsetPage<any>>(`/payouts${qs({ status: get('status') || undefined, partner_id: get('partner_id') || undefined, page })}`),
  });
  return (
    <FinanceGate>
      <PageTitle title="Выплаты" />
      <div className="flex gap-2 mb-3">
        <select className="ui-input h-8 w-40" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">Статус</option>
          <option value="pending">Ожидает</option>
          <option value="paid">Выплачено</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'payout', header: 'Выплата' },
            { key: 'partner', header: 'Партнёр' },
            { key: 'amount', header: 'Сумма', align: 'right' },
            { key: 'status', header: 'Статус' },
            { key: 'period', header: 'Период' },
            { key: 'paid', header: 'Выплачено' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            payout: <EntityLink type="payout" id={row.id}>#{row.id}</EntityLink>,
            partner: <EntityLink type="partner" id={row.partner_id}>{row.partner_name}</EntityLink>,
            amount: `${formatNumber(row.amount)} ${row.currency || ''}`.trim(),
            status: <StatusBadge status={row.status} />,
            period: formatDateTime(row.period),
            paid: formatDateTime(row.paid_at),
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(p) => set({ page: String(p) })} />
      </QueryState>
    </FinanceGate>
  );
}

export function PayoutDetailPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ['payout', id], queryFn: () => api.get<any>(`/payouts/${id}`) });
  const data = query.data;
  return (
    <FinanceGate>
      <QueryState loading={query.isLoading} error={query.error}>
        {data && (
          <div className="space-y-4">
            <PageTitle title={`Выплата #${data.id}`} />
            <div className="ui-card p-4">
              <Kv label="Партнёр"><EntityLink type="partner" id={data.partner_id}>{data.partner_name}</EntityLink></Kv>
              <Kv label="Сумма">{formatNumber(data.amount)} {data.currency}</Kv>
              <Kv label="Статус"><StatusBadge status={data.status} /></Kv>
              <Kv label="Создана">{formatDateTime(data.created_at)}</Kv>
              <Kv label="Выплачено">{formatDateTime(data.paid_at)}</Kv>
            </div>
            <DataTable
              columns={[
                { key: 'commission', header: 'Комиссия' },
                { key: 'conversion', header: 'Конверсия' },
                { key: 'amount', header: 'Сумма', align: 'right' },
              ]}
              rows={(data.items || []).map((row: any) => ({
                id: row.id,
                commission: <EntityLink type="commission" id={row.commission_id}>#{row.commission_id}</EntityLink>,
                conversion: row.conversion_id ? <EntityLink type="conversion" id={row.conversion_id}>#{row.conversion_id}</EntityLink> : '—',
                amount: formatNumber(row.amount),
              }))}
            />
          </div>
        )}
      </QueryState>
    </FinanceGate>
  );
}

export function AuditPage() {
  const { get, set } = useQueryState();
  const query = useQuery({
    queryKey: ['audit', get('cursor'), get('action'), get('entity_type'), get('entity_id'), get('admin_user_id')],
    queryFn: () =>
      api.get<{ items: any[]; next_cursor: string | null; has_more: boolean }>(
        `/audit${qs({
          cursor: get('cursor') || undefined,
          action: get('action') || undefined,
          entity_type: get('entity_type') || undefined,
          entity_id: get('entity_id') || undefined,
          admin_user_id: get('admin_user_id') || undefined,
        })}`,
      ),
  });
  return (
    <div>
      <PageTitle title="Аудит" />
      <div className="flex flex-wrap gap-2 mb-3">
        <input className="ui-input h-8 w-40" placeholder="ID админа" defaultValue={get('admin_user_id')} onBlur={(e) => set({ admin_user_id: e.target.value })} />
        <input className="ui-input h-8 w-48" placeholder="Действие" defaultValue={get('action')} onBlur={(e) => set({ action: e.target.value })} />
        <input className="ui-input h-8 w-40" placeholder="Тип сущности" defaultValue={get('entity_type')} onBlur={(e) => set({ entity_type: e.target.value })} />
        <input className="ui-input h-8 w-40" placeholder="ID сущности" defaultValue={get('entity_id')} onBlur={(e) => set({ entity_id: e.target.value })} />
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'time', header: 'Время' },
            { key: 'admin', header: 'Админ' },
            { key: 'action', header: 'Действие' },
            { key: 'entity', header: 'Сущность' },
            { key: 'reason', header: 'Причина' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: row.id,
            time: formatDateTime(row.created_at),
            admin: row.admin_email,
            action: row.action,
            entity: (
              <span>
                {row.entity_type} / <CopyId value={row.entity_id} />
              </span>
            ),
            reason: row.reason,
          }))}
        />
        {query.data?.has_more && (
          <div className="flex justify-end mt-3">
            <button type="button" className="ui-input !w-auto h-8" onClick={() => set({ cursor: query.data?.next_cursor || undefined })}>
              Показать ещё
            </button>
          </div>
        )}
      </QueryState>
    </div>
  );
}
