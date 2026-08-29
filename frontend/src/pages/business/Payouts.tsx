import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { cn } from '@/shared/utils/cn';

interface Payout {
  id: string;
  partner_name: string;
  amount: number;
  currency: string;
  status: string;
  period_start: string;
  period_end: string;
  created_at: string;
}

interface PayoutsResponse {
  items: Payout[];
  total: number;
}

const tabs = [
  { key: 'all', label: 'Все' },
  { key: 'pending', label: 'Ожидание' },
  { key: 'processing', label: 'В обработке' },
  { key: 'paid', label: 'Выплачены' },
];

const statusLabels: Record<string, { label: string; className: string }> = {
  pending: { label: 'Ожидание', className: 'bg-yellow-50 text-yellow-700' },
  processing: { label: 'В обработке', className: 'bg-blue-50 text-blue-700' },
  paid: { label: 'Выплачено', className: 'bg-accent text-primary' },
  cancelled: { label: 'Отменено', className: 'bg-red-50 text-red-700' },
};

export function BusinessPayouts() {
  const [activeTab, setActiveTab] = useState('all');

  const { data, isLoading } = useQuery<PayoutsResponse>({
    queryKey: ['business', 'payouts', activeTab],
    queryFn: () => api.get(`/business/payouts${activeTab !== 'all' ? `?status=${activeTab}` : ''}`),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="ui-page-title">Выплаты</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">Механизм выплат скоро появится.</p>
      </div>

      <div className="flex gap-1 bg-muted rounded-lg p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : !data?.items?.length ? (
        <EmptyState
          title="Нет выплат"
          description="Выплаты формируются автоматически по завершении hold-периода конверсий."
        />
      ) : (
        <div className="ui-card overflow-hidden">
          <table className="ui-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Партнёр</th>
                <th>Период</th>
                <th className="!text-right">Сумма</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((payout) => {
                const status = statusLabels[payout.status] || statusLabels.pending;
                return (
                  <tr key={payout.id}>
                    <td className="text-muted-foreground">
                      {new Date(payout.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="font-medium">{payout.partner_name}</td>
                    <td className="text-muted-foreground">
                      {new Date(payout.period_start).toLocaleDateString('ru-RU')} — {new Date(payout.period_end).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="text-right font-medium">{payout.amount.toLocaleString()} {payout.currency}</td>
                    <td>
                      <span className={cn('ui-badge', status.className)}>
                        {status.label}
                      </span>
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
