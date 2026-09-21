import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { StatCard } from '@/shared/components/StatCard';
import { formatMoney } from '@/shared/utils/format';
import { Wallet, Clock3, Banknote, Hourglass } from 'lucide-react';
import { TestModeBanner } from '@/shared/finance/banners';
import { financeReasonText, type FinancialMode } from '@/shared/finance/messages';
import { Link } from 'react-router-dom';
import { cn } from '@/shared/utils/cn';

interface PayoutCommission {
  id: number;
  amount: number;
  currency: string;
  conversion: {
    id: number | null;
    created_at: string | null;
    amount: number | null;
    offer: {
      id: number | null;
      name: string | null;
    };
  };
}

interface PartnerPayout {
  id: number;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
  paid_at: string | null;
  period_start: string | null;
  period_end: string | null;
  provider_transaction_id: string | null;
  business: {
    id: number | null;
    name: string | null;
  } | null;
  commissions?: PayoutCommission[];
}

interface PayoutsData extends FinancialMode {
  pending: number;
  hold: number;
  available: number;
  available_amount: number;
  payout_pending: number;
  paid: number;
  payouts: PartnerPayout[];
  payout_eligibility?: { eligible: boolean; reason_code?: string | null; reason_message?: string | null };
}

const statusMap: Record<string, { label: string; className: string }> = {
  created: { label: 'Создана', className: 'bg-yellow-50 text-yellow-700' },
  awaiting_confirmation: { label: 'К выплате', className: 'bg-yellow-50 text-yellow-700' },
  processing: { label: 'Ожидает выплаты', className: 'bg-blue-50 text-blue-700' },
  paid: { label: 'Выплачено', className: 'bg-accent text-primary' },
  failed: { label: 'Ошибка', className: 'bg-red-50 text-red-700' },
  overdue: { label: 'Просрочено бизнесом', className: 'bg-red-50 text-red-700' },
  cancelled: { label: 'Отменено', className: 'bg-red-50 text-red-700' },
  manual_review: { label: 'На проверке', className: 'bg-orange-50 text-orange-700' },
};

function businessName(payout: PartnerPayout) {
  return payout.business?.name?.trim() || '—';
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('ru-RU');
}

function formatPeriod(start?: string | null, end?: string | null) {
  if (!start && !end) return '—';
  if (start && end) {
    const a = formatDate(start);
    const b = formatDate(end);
    return a === b ? a : `${a} — ${b}`;
  }
  return formatDate(start || end);
}

function money(value: number | null | undefined, currency = 'RUB') {
  if (value === null || value === undefined) return '—';
  return formatMoney(value, currency === 'RUB' ? '₽' : currency);
}

export function PartnerPayouts() {
  const [selected, setSelected] = useState<PartnerPayout | null>(null);
  const { data, isLoading } = useQuery<PayoutsData>({
    queryKey: ['partner', 'payouts'],
    queryFn: () => api.get('/partner/payouts'),
  });

  if (isLoading) {
    return (
      <div className="space-y-5">
        <h1 className="ui-page-title">Начисления и выплаты</h1>
        <Skeleton className="h-28 rounded-xl" />
      </div>
    );
  }

  const eligibility = data?.payout_eligibility;

  return (
    <div className="space-y-5">
      <h1 className="ui-page-title">Начисления и выплаты</h1>
      <TestModeBanner visible={data?.financial_mode === 'TEST'} />
      {eligibility && !eligibility.eligible && (
        <div className="rounded-lg border border-warning/30 bg-orange-50 px-4 py-3 text-sm text-warning">
          <p className="font-medium">Выплаты пока недоступны</p>
          <p className="mt-0.5">{financeReasonText(eligibility.reason_code, eligibility.reason_message)}</p>
          <Link to="/partner/settings" className="mt-2 inline-block text-sm font-medium underline">
            {eligibility.reason_code === 'PAYOUT_PROFILE_MISSING' ||
            eligibility.reason_code === 'PAYMENT_DETAILS_INVALID' ||
            eligibility.reason_code === 'PAYOUT_PROFILE_NOT_VERIFIED'
              ? 'Заполнить реквизиты для выплат'
              : 'Заполнить юридические данные и реквизиты'}
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        <StatCard title="Ожидает подтверждения" value={formatMoney(data?.pending, '₽')} icon={Hourglass} tone="orange" />
        <StatCard title="На hold" value={formatMoney(data?.hold, '₽')} icon={Clock3} tone="blue" />
        <StatCard title="Доступно к выплате" value={formatMoney(data?.available, '₽')} icon={Wallet} tone="teal" />
        <StatCard title="Ожидает выплаты" value={formatMoney(data?.payout_pending, '₽')} icon={Banknote} tone="blue" />
        <StatCard title="Выплачено" value={formatMoney(data?.paid, '₽')} icon={Banknote} tone="purple" />
      </div>
      <p className="text-sm text-muted-foreground">
        RefIQ не хранит деньги партнёра. Суммы ниже — начисленные обязательства бизнеса.
      </p>

      {!data?.payouts?.length ? (
        <EmptyState title="Выплат пока нет" description="Здесь будет история выплат от бизнесов." />
      ) : (
        <div className="ui-card overflow-x-auto">
          <table className="ui-table table-fixed min-w-[640px]">
            <colgroup>
              <col className="w-[20%]" />
              <col />
              <col className="w-[150px]" />
              <col className="w-[200px]" />
            </colgroup>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Бизнес</th>
                <th className="!text-right">Сумма</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {data.payouts.map((p) => {
                const status = statusMap[p.status] || statusMap.awaiting_confirmation;
                return (
                  <tr
                    key={p.id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Выплата #${p.id}`}
                    className="cursor-pointer focus-visible:outline-none focus-visible:bg-muted/60"
                    onClick={() => setSelected(p)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setSelected(p);
                      }
                    }}
                  >
                    <td className="text-muted-foreground whitespace-nowrap">{formatDate(p.created_at)}</td>
                    <td className="font-medium min-w-0 truncate">{businessName(p)}</td>
                    <td className="text-right font-medium whitespace-nowrap tabular-nums">
                      {money(p.amount, p.currency)}
                    </td>
                    <td>
                      <span className={cn('ui-badge', status.className)}>{status.label}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && <PayoutDetailDrawer payout={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function PayoutDetailDrawer({ payout, onClose }: { payout: PartnerPayout; onClose: () => void }) {
  const status = statusMap[payout.status] || statusMap.awaiting_confirmation;
  const commissions = payout.commissions || [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <aside className="relative ui-card w-full max-w-lg h-full shadow-soft flex flex-col border-l">
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border/70">
          <div className="min-w-0">
            <h2 className="ui-section-title">Выплата #{payout.id}</h2>
            <p className="mt-1 text-sm text-muted-foreground truncate">{businessName(payout)}</p>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-5">
          <div className="space-y-3">
            <DetailRow label="Бизнес">{businessName(payout)}</DetailRow>
            <DetailRow label="Сумма">{money(payout.amount, payout.currency)}</DetailRow>
            <DetailRow label="Статус">
              <span className={cn('ui-badge', status.className)}>{status.label}</span>
            </DetailRow>
            <DetailRow label="Период">{formatPeriod(payout.period_start, payout.period_end)}</DetailRow>
            <DetailRow label="Payout ID">
              <span className="font-mono text-sm">{payout.id}</span>
            </DetailRow>
            {payout.paid_at && <DetailRow label="Дата выплаты">{formatDate(payout.paid_at)}</DetailRow>}
            <DetailRow label="Транзакция">{payout.provider_transaction_id || '—'}</DetailRow>
          </div>

          <div>
            <h3 className="ui-section-title mb-3">Включённые начисления</h3>
            {!commissions.length ? (
              <p className="text-sm text-muted-foreground">Начисления не найдены.</p>
            ) : (
              <div className="rounded-lg border border-border/70 overflow-hidden">
                <div className="max-h-[min(50vh,360px)] overflow-auto">
                  <table className="ui-table">
                    <thead className="sticky top-0 bg-card">
                      <tr>
                        <th>Дата</th>
                        <th>Конверсия</th>
                        <th>Оффер</th>
                        <th className="!text-right">Сумма</th>
                        <th className="!text-right">Комиссия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {commissions.map((row) => (
                        <tr key={row.id}>
                          <td className="whitespace-nowrap text-muted-foreground">
                            {formatDate(row.conversion.created_at)}
                          </td>
                          <td className="whitespace-nowrap font-mono text-xs">
                            {row.conversion.id != null ? `#${row.conversion.id}` : '—'}
                          </td>
                          <td className="min-w-0 max-w-[140px] truncate">
                            {row.conversion.offer.name || '—'}
                          </td>
                          <td className="text-right whitespace-nowrap tabular-nums">
                            {money(row.conversion.amount, row.currency)}
                          </td>
                          <td className="text-right whitespace-nowrap tabular-nums font-medium">
                            {money(row.amount, row.currency)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 text-sm items-start">
      <span className="text-muted-foreground">{label}</span>
      <div className="font-medium min-w-0 break-words">{children}</div>
    </div>
  );
}
