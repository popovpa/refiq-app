import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { StatCard } from '@/shared/components/StatCard';
import { formatMoney } from '@/shared/utils/format';
import { Wallet, Clock3, Banknote } from 'lucide-react';

interface PayoutsData {
  available_amount: number;
  payouts: Array<{
    id: string;
    amount: number;
    currency: string;
    status: string;
    created_at: string;
    paid_at: string | null;
  }>;
}

const statusMap: Record<string, { label: string; className: string }> = {
  pending: { label: 'Ожидает', className: 'bg-yellow-50 text-yellow-700' },
  processing: { label: 'В обработке', className: 'bg-blue-50 text-blue-700' },
  paid: { label: 'Выплачено', className: 'bg-accent text-primary' },
  failed: { label: 'Ошибка', className: 'bg-red-50 text-red-700' },
};

export function PartnerPayouts() {
  const { data, isLoading } = useQuery<PayoutsData>({
    queryKey: ['partner', 'payouts'],
    queryFn: () => api.get('/partner/payouts'),
  });

  if (isLoading) {
    return (
      <div className="space-y-5">
        <h1 className="ui-page-title">Выплаты</h1>
        <Skeleton className="h-28 rounded-xl" />
      </div>
    );
  }

  const paid = (data?.payouts || [])
    .filter((p) => p.status === 'paid')
    .reduce((sum, p) => sum + p.amount, 0);

  return (
    <div className="space-y-5">
      <h1 className="ui-page-title">Выплаты</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard
          title="Доступно к выплате"
          value={formatMoney(data?.available_amount, '₽')}
          icon={Wallet}
          tone="teal"
        />
        <StatCard
          title="В обработке"
          value={formatMoney(
            (data?.payouts || [])
              .filter((p) => p.status === 'processing' || p.status === 'pending')
              .reduce((s, p) => s + p.amount, 0),
            '₽',
          )}
          icon={Clock3}
          tone="orange"
        />
        <StatCard title="Выплачено" value={formatMoney(paid, '₽')} icon={Banknote} tone="purple" />
      </div>

      {!data?.payouts?.length ? (
        <EmptyState
          title="Выплат пока нет"
          description="Здесь будет отображаться история ваших выплат."
        />
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
                const status = statusMap[p.status] || statusMap.pending;
                return (
                  <tr key={p.id}>
                    <td className="text-muted-foreground">
                      {new Date(p.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="text-right font-medium">
                      {formatMoney(p.amount, p.currency || '₽')}
                    </td>
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
