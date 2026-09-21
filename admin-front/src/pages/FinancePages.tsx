import type { ReactNode } from 'react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api, qs } from '@/lib/api';
import { useQueryState } from '@/lib/url';
import { useAuth } from '@/lib/auth';
import { ADMIN_FINANCE } from '@/lib/permissions';
import { CopyId, EmptyState, Kv, PageTitle, StatusBadge, formatDateTime, formatNumber } from '@/components/ui';
import { DataTable, OffsetPager, QueryState } from '@/components/Table';
import { EntityLink } from '@/components/EntityLink';
import { RqcidLink } from '@/components/RqcidLink';
import { actorTypeLabel, auditEventLabel, entityTypeLabel } from '@/lib/labels';

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
  const source = get('source') || 'events';
  return (
    <div>
      <PageTitle title="Аудит" />
      <div className="flex gap-2 mb-4">
        <button
          type="button"
          className={`h-8 px-3 rounded-md text-sm ${source === 'events' ? 'bg-primary text-primary-foreground' : 'ui-input !w-auto'}`}
          onClick={() => set({ source: 'events' })}
        >
          События
        </button>
        <button
          type="button"
          className={`h-8 px-3 rounded-md text-sm ${source === 'admin' ? 'bg-primary text-primary-foreground' : 'ui-input !w-auto'}`}
          onClick={() => set({ source: 'admin' })}
        >
          Действия админов
        </button>
      </div>
      {source === 'admin' ? <AdminAuditTable /> : <CanonicalAuditTable />}
    </div>
  );
}

function AdminAuditTable() {
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
    <>
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
    </>
  );
}

function CanonicalAuditTable() {
  const { get, set } = useQueryState();
  const [selected, setSelected] = useState<any | null>(null);
  const query = useQuery({
    queryKey: [
      'audit-events',
      get('cursor'),
      get('date_from'),
      get('date_to'),
      get('event_type'),
      get('entity_type'),
      get('entity_id'),
      get('actor_type'),
      get('business_id'),
      get('request_id'),
    ],
    queryFn: () =>
      api.get<{ items: any[]; next_cursor: string | null; has_more: boolean }>(
        `/audit/events${qs({
          cursor: get('cursor') || undefined,
          date_from: get('date_from') ? `${get('date_from')}T00:00:00` : undefined,
          date_to: get('date_to') ? `${get('date_to')}T23:59:59` : undefined,
          event_type: get('event_type') || undefined,
          entity_type: get('entity_type') || undefined,
          entity_id: get('entity_id') || undefined,
          actor_type: get('actor_type') || undefined,
          business_id: get('business_id') || undefined,
          request_id: get('request_id') || undefined,
        })}`,
      ),
  });
  const items = query.data?.items || [];
  return (
    <>
      <div className="flex flex-wrap gap-2 mb-3">
        <input className="ui-input h-8 w-40" type="date" defaultValue={get('date_from')} onBlur={(e) => set({ date_from: e.target.value })} />
        <input className="ui-input h-8 w-40" type="date" defaultValue={get('date_to')} onBlur={(e) => set({ date_to: e.target.value })} />
        <select className="ui-input h-8 w-56" value={get('event_type')} onChange={(e) => set({ event_type: e.target.value })}>
          <option value="">Все события</option>
          <option value="OFFER_CREATED">Оффер создан</option>
          <option value="OFFER_UPDATED">Оффер изменён</option>
          <option value="OFFER_STATUS_CHANGED">Статус оффера изменён</option>
          <option value="OFFER_HOLD_CHANGED">Холд оффера изменён</option>
          <option value="OFFER_TRAFFIC_POLICY_CHANGED">Политика трафика</option>
          <option value="OFFER_ACCESS_POLICY_CHANGED">Политика доступа</option>
          <option value="OFFER_PRODUCT_CHANGED">Продукт оффера</option>
        </select>
        <select className="ui-input h-8 w-36" value={get('entity_type')} onChange={(e) => set({ entity_type: e.target.value })}>
          <option value="">Сущность</option>
          <option value="OFFER">Оффер</option>
        </select>
        <input className="ui-input h-8 w-32" placeholder="ID сущности" defaultValue={get('entity_id')} onBlur={(e) => set({ entity_id: e.target.value })} />
        <select className="ui-input h-8 w-40" value={get('actor_type')} onChange={(e) => set({ actor_type: e.target.value })}>
          <option value="">Инициатор</option>
          <option value="USER">Пользователь</option>
          <option value="ADMIN">Админ</option>
          <option value="SYSTEM">Система</option>
        </select>
        <input className="ui-input h-8 w-32" placeholder="Business ID" defaultValue={get('business_id')} onBlur={(e) => set({ business_id: e.target.value })} />
        <input className="ui-input h-8 w-48" placeholder="Request ID" defaultValue={get('request_id')} onBlur={(e) => set({ request_id: e.target.value })} />
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!items.length}>
        <DataTable
          columns={[
            { key: 'time', header: 'Дата и время' },
            { key: 'event', header: 'Событие' },
            { key: 'entity', header: 'Сущность' },
            { key: 'entityId', header: 'ID сущности' },
            { key: 'actor', header: 'Инициатор' },
            { key: 'business', header: 'Business' },
            { key: 'changes', header: 'Изменения' },
          ]}
          rows={items.map((row: any) => ({
            id: row.id,
            time: formatDateTime(row.created_at),
            event: auditEventLabel(row.event_type),
            entity: entityTypeLabel(row.entity_type),
            entityId: <CopyId value={row.entity_id} />,
            actor: actorSummary(row),
            business: row.actor_business_id ?? row.metadata?.business_id ?? '—',
            changes: changeSummary(row.changes),
            raw: row,
          }))}
          onRowClick={(row) => setSelected((row as any).raw)}
        />
        {query.data?.has_more && (
          <div className="flex justify-end mt-3">
            <button type="button" className="ui-input !w-auto h-8" onClick={() => set({ cursor: query.data?.next_cursor || undefined })}>
              Показать ещё
            </button>
          </div>
        )}
      </QueryState>
      {selected && <AuditEventModal event={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function actorSummary(row: any) {
  const kind = actorTypeLabel(row.actor_type);
  const id = row.actor_user_id ?? row.actor_admin_id;
  return id ? `${kind} #${id}` : kind;
}

function formatChangeValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function changeSummary(changes?: Record<string, { before?: unknown; after?: unknown }> | null) {
  if (!changes || !Object.keys(changes).length) return '—';
  return Object.entries(changes)
    .map(([field, value]) => `${field}: ${formatChangeValue(value?.before)} → ${formatChangeValue(value?.after)}`)
    .join(', ');
}

function AuditEventModal({ event, onClose }: { event: any; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-2xl max-h-[90vh] overflow-auto p-5 space-y-3 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">{auditEventLabel(event.event_type)}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <Kv label="Событие">{auditEventLabel(event.event_type)}</Kv>
        <Kv label="Дата и время">{formatDateTime(event.created_at)}</Kv>
        <Kv label="Сущность">{entityTypeLabel(event.entity_type)}</Kv>
        <Kv label="ID сущности"><CopyId value={event.entity_id} /></Kv>
        <Kv label="Инициатор">{actorSummary(event)}</Kv>
        <Kv label="Business">{event.actor_business_id ?? event.metadata?.business_id ?? '—'}</Kv>
        <Kv label="Request ID"><CopyId value={event.request_id} /></Kv>
        <Kv label="IP">{event.ip_address || '—'}</Kv>
        <Kv label="User-Agent">{event.user_agent || '—'}</Kv>
        <Kv label="Операция">{event.source_operation || '—'}</Kv>
        <Kv label="Причина">{event.reason || '—'}</Kv>
        <Kv label="Изменения">
          <div className="space-y-1">
            {event.changes && Object.keys(event.changes).length
              ? Object.entries(event.changes).map(([field, value]: [string, any]) => (
                  <div key={field}>
                    {field}: {formatChangeValue(value?.before)} → {formatChangeValue(value?.after)}
                  </div>
                ))
              : '—'}
          </div>
        </Kv>
        <Kv label="Metadata">
          {event.metadata
            ? Object.entries(event.metadata)
                .map(([key, value]) => `${key}: ${formatChangeValue(value)}`)
                .join(', ')
            : '—'}
        </Kv>
      </div>
    </div>
  );
}
