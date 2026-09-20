import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { StatCard } from '@/shared/components/StatCard';
import { formatMoney } from '@/shared/utils/format';
import { Wallet, Clock3, Banknote, Hourglass } from 'lucide-react';
import { TestModeBanner } from '@/shared/finance/banners';
import { financeReasonText, type FinancialMode } from '@/shared/finance/messages';
import { Link } from 'react-router-dom';

interface PayoutsData extends FinancialMode {
  pending: number;
  hold: number;
  available: number;
  available_amount: number;
  payout_pending: number;
  paid: number;
  payouts: Array<{
    id: number;
    amount: number;
    currency: string;
    status: string;
    created_at: string;
    paid_at: string | null;
  }>;
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

export function PartnerPayouts() {
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
          <table className="ui-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th className="text-right">Сумма</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {data.payouts.map((p) => {
                const status = statusMap[p.status] || statusMap.awaiting_confirmation;
                return (
                  <tr key={p.id}>
                    <td className="text-muted-foreground">{new Date(p.created_at).toLocaleDateString('ru-RU')}</td>
                    <td className="text-right font-medium">{formatMoney(p.amount, p.currency === 'RUB' ? '₽' : p.currency)}</td>
                    <td>
                      <span className={`ui-badge ${status.className}`}>{status.label}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
