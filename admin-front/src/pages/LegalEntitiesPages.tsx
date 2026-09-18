import { useState, type ReactNode } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api, errorMessage, qs } from '@/lib/api';
import { useQueryState } from '@/lib/url';
import { useAuth } from '@/lib/auth';
import { ADMIN_FINANCE } from '@/lib/permissions';
import { Button, EmptyState, Kv, PageTitle, StatusBadge, formatDateTime, useToast } from '@/components/ui';
import { DataTable, OffsetPager, QueryState } from '@/components/Table';
import { EntityLink } from '@/components/EntityLink';
import { canManuallyReviewLegalEntity, ownerTypeLabel, REJECT_REASON_OPTIONS } from '@/lib/legalEntity';

type OffsetPage<T> = { items: T[]; page: number; pages: number };

function FinanceGate({ children }: { children: ReactNode }) {
  const { has } = useAuth();
  if (!has(ADMIN_FINANCE)) {
    return <EmptyState title="Недостаточно прав" description="Для этого раздела нужна роль ADMIN_FINANCE." />;
  }
  return <>{children}</>;
}

function ownerCell(row: any) {
  if (row.owner_type === 'business' || row.owner_type === 'shared') {
    return (
      <span>
        <EntityLink type="business" id={row.business_id}>{row.business_name || `Бизнес #${row.business_id}`}</EntityLink>
        {row.owner_type === 'shared' && row.partner_id ? (
          <>
            {' / '}
            <EntityLink type="partner" id={row.partner_id}>{row.partner_name || `Партнёр #${row.partner_id}`}</EntityLink>
          </>
        ) : null}
      </span>
    );
  }
  if (row.owner_type === 'partner') {
    return <EntityLink type="partner" id={row.partner_id}>{row.partner_name || `Партнёр #${row.partner_id}`}</EntityLink>;
  }
  return '—';
}

export function LegalEntitiesPage() {
  const { get, set } = useQueryState();
  const page = Number(get('page') || 1);
  const query = useQuery({
    queryKey: ['legal-entities', get('status'), get('owner_type'), page],
    queryFn: () =>
      api.get<OffsetPage<any>>(
        `/legal-entities${qs({
          status: get('status') || undefined,
          owner_type: get('owner_type') || undefined,
          page,
        })}`,
      ),
  });
  return (
    <FinanceGate>
      <PageTitle title="Юридические данные" />
      <div className="flex flex-wrap gap-2 mb-3">
        <select className="ui-input h-8 w-56" value={get('status')} onChange={(e) => set({ status: e.target.value })}>
          <option value="">Все статусы</option>
          <option value="PENDING_VERIFICATION">На проверке</option>
          <option value="VERIFIED">Подтверждено</option>
          <option value="REJECTED">Отклонено</option>
          <option value="REVIEW_REQUIRED">Требуется проверка</option>
          <option value="BLOCKED">Заблокировано</option>
        </select>
        <select className="ui-input h-8 w-40" value={get('owner_type')} onChange={(e) => set({ owner_type: e.target.value })}>
          <option value="">Все субъекты</option>
          <option value="business">Бизнес</option>
          <option value="partner">Партнёр</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error} empty={!query.data?.items.length}>
        <DataTable
          columns={[
            { key: 'id', header: 'ID' },
            { key: 'owner', header: 'Владелец' },
            { key: 'context', header: 'Контекст' },
            { key: 'subject', header: 'Тип' },
            { key: 'name', header: 'Наименование' },
            { key: 'inn', header: 'ИНН' },
            { key: 'ogrn', header: 'ОГРН / ОГРНИП' },
            { key: 'tax', header: 'Налог' },
            { key: 'status', header: 'Статус' },
            { key: 'created', header: 'Создано' },
            { key: 'updated', header: 'Обновлено' },
          ]}
          rows={(query.data?.items || []).map((row: any) => ({
            id: <EntityLink type="legal_entity" id={row.id}>{row.id}</EntityLink>,
            owner: (
              <div>
                {ownerCell(row)}
                <div className="text-xs text-muted-foreground">{row.owner_email || '—'}</div>
              </div>
            ),
            context: ownerTypeLabel(row.owner_type),
            subject: row.subject_type,
            name: (
              <EntityLink type="legal_entity" id={row.id}>
                {row.display_name || row.legal_name || row.full_name || `#${row.id}`}
              </EntityLink>
            ),
            inn: row.inn || '—',
            ogrn: row.ogrn || row.ogrnip || '—',
            tax: row.tax_status,
            status: <StatusBadge status={row.verification_status} />,
            created: formatDateTime(row.created_at),
            updated: formatDateTime(row.updated_at),
          }))}
        />
        <OffsetPager page={page} pages={query.data?.pages || 1} onPage={(p) => set({ page: String(p) })} />
      </QueryState>
    </FinanceGate>
  );
}

export function LegalEntityDetailPage() {
  const { id } = useParams();
  const toast = useToast();
  const qc = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const query = useQuery({ queryKey: ['legal-entity', id], queryFn: () => api.get<any>(`/legal-entities/${id}`) });
  const data = query.data;

  const verify = useMutation({
    mutationFn: () => api.post(`/legal-entities/${id}/verify`, { comment: 'Проверено вручную' }),
    onSuccess: (next) => {
      toast.addToast('Юридические данные подтверждены', 'success');
      qc.setQueryData(['legal-entity', id], next);
      qc.invalidateQueries({ queryKey: ['legal-entities'] });
      setConfirmOpen(false);
    },
    onError: (err) => toast.addToast(errorMessage(err), 'error'),
  });
  const reject = useMutation({
    mutationFn: (payload: { reason_code: string; comment?: string }) => api.post(`/legal-entities/${id}/reject`, payload),
    onSuccess: (next) => {
      toast.addToast('Юридические данные отклонены', 'success');
      qc.setQueryData(['legal-entity', id], next);
      qc.invalidateQueries({ queryKey: ['legal-entities'] });
      setRejectOpen(false);
    },
    onError: (err) => toast.addToast(errorMessage(err), 'error'),
  });

  const canReview = canManuallyReviewLegalEntity(data?.verification_status);

  return (
    <FinanceGate>
      <QueryState loading={query.isLoading} error={query.error}>
        {data && (
          <div className="space-y-4">
            <PageTitle
              title={`Юридические данные #${data.id}`}
              actions={
                canReview ? (
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => setConfirmOpen(true)}>
                      Подтвердить
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => setRejectOpen(true)}>
                      Отклонить
                    </Button>
                  </div>
                ) : null
              }
            />
            <div className="ui-card p-4">
              <Kv label="Контекст">{ownerTypeLabel(data.owner_type)}</Kv>
              <Kv label="Бизнес">
                {data.business_id ? <EntityLink type="business" id={data.business_id}>{data.business_name}</EntityLink> : '—'}
              </Kv>
              <Kv label="Партнёр">
                {data.partner_id ? <EntityLink type="partner" id={data.partner_id}>{data.partner_name}</EntityLink> : '—'}
              </Kv>
              <Kv label="Владелец">{data.owner_email || '—'}</Kv>
              <Kv label="Тип субъекта">{data.subject_type}</Kv>
              <Kv label="Налоговый статус">{data.tax_status}</Kv>
              <Kv label="ИНН">{data.inn || '—'}</Kv>
              <Kv label="КПП">{data.kpp || '—'}</Kv>
              <Kv label="ОГРН">{data.ogrn || '—'}</Kv>
              <Kv label="ОГРНИП">{data.ogrnip || '—'}</Kv>
              <Kv label="Наименование">{data.legal_name || '—'}</Kv>
              <Kv label="ФИО">{data.full_name || '—'}</Kv>
              <Kv label="Адрес">{data.legal_address || '—'}</Kv>
              <Kv label="Статус"><StatusBadge status={data.verification_status} /></Kv>
              <Kv label="Источник">{data.verification_source || '—'}</Kv>
              <Kv label="Справочник">{data.lookup_provider || '—'}</Kv>
              {data.lookup_invalid ? (
                <Kv label="Предупреждение">Справочник пометил запись как некорректную. Не подтверждать без ручной проверки.</Kv>
              ) : null}
              <Kv label="Создано">{formatDateTime(data.created_at)}</Kv>
              <Kv label="Обновлено">{formatDateTime(data.updated_at)}</Kv>
            </div>
            <div>
              <h2 className="ui-section-title mb-2">История проверок</h2>
              <DataTable
                columns={[
                  { key: 'date', header: 'Дата' },
                  { key: 'provider', header: 'Провайдер' },
                  { key: 'result', header: 'Результат' },
                  { key: 'admin', header: 'Админ' },
                  { key: 'reason', header: 'Причина' },
                  { key: 'comment', header: 'Комментарий' },
                ]}
                rows={(data.attempts || []).map((row: any) => ({
                  id: row.id,
                  date: formatDateTime(row.completed_at || row.requested_at),
                  provider: row.provider,
                  result: <StatusBadge status={row.status} />,
                  admin: row.actor_admin_email || '—',
                  reason: row.reason_code || '—',
                  comment: row.comment || '—',
                }))}
              />
            </div>
          </div>
        )}
      </QueryState>
      {confirmOpen && (
        <ConfirmModal
          title="Подтвердить юридические данные?"
          description="После подтверждения субъект сможет использовать финансовые функции, требующие VERIFIED status."
          confirmLabel="Подтвердить"
          pending={verify.isPending}
          onClose={() => setConfirmOpen(false)}
          onConfirm={() => verify.mutate()}
        />
      )}
      {rejectOpen && (
        <RejectModal
          pending={reject.isPending}
          onClose={() => setRejectOpen(false)}
          onConfirm={(payload) => reject.mutate(payload)}
        />
      )}
    </FinanceGate>
  );
}

function ConfirmModal({
  title,
  description,
  confirmLabel,
  onConfirm,
  onClose,
  pending,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  pending?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">{title}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <p className="text-sm text-muted-foreground">{description}</p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={onConfirm} disabled={pending}>
            {pending ? 'Выполняется…' : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

function RejectModal({
  pending,
  onClose,
  onConfirm,
}: {
  pending?: boolean;
  onClose: () => void;
  onConfirm: (payload: { reason_code: string; comment?: string }) => void;
}) {
  const [reason, setReason] = useState<string>(REJECT_REASON_OPTIONS[0].value);
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    if (reason === 'OTHER' && !comment.trim()) {
      setError('Для причины «Другое» нужен комментарий');
      return;
    }
    onConfirm({ reason_code: reason, comment: comment.trim() || undefined });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">Отклонить юридические данные</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <div>
          <label className="ui-label" htmlFor="reject-reason">
            Причина
          </label>
          <select
            id="reject-reason"
            className="ui-input"
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setError(null);
            }}
          >
            {REJECT_REASON_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="ui-label" htmlFor="reject-comment">
            Комментарий
          </label>
          <textarea
            id="reject-comment"
            className="ui-input min-h-[88px] py-2"
            value={comment}
            onChange={(e) => {
              setComment(e.target.value);
              setError(null);
            }}
          />
          {error && <p className="text-xs text-destructive mt-1">{error}</p>}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="destructive" onClick={submit} disabled={pending}>
            {pending ? 'Выполняется…' : 'Отклонить'}
          </Button>
        </div>
      </div>
    </div>
  );
}
