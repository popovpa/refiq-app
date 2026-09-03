import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { formatMoney } from '@/shared/utils/format';
import { DateRangeSelector } from '@/shared/dateRange/DateRangeSelector';
import { useDateRange, withDateRangeQuery } from '@/shared/dateRange';

interface Conversion {
  id: string;
  offer_id: string;
  offer_name?: string | null;
  click_id: string | null;
  external_id: string | null;
  amount: number;
  currency: string;
  commission_amount: number;
  status: string;
  created_at: string;
}

const statusMap: Record<string, { label: string; className: string }> = {
  pending: { label: 'Ожидание', className: 'bg-yellow-50 text-yellow-700' },
  approved: { label: 'Одобрена', className: 'bg-accent text-primary' },
  rejected: { label: 'Отклонена', className: 'bg-red-50 text-red-700' },
  paid: { label: 'Выплачена', className: 'bg-blue-50 text-blue-700' },
};

export function PartnerConversions() {
  const range = useDateRange();
  const { data, isLoading } = useQuery<{ items: Conversion[]; total: number }>({
    queryKey: ['partner', 'conversions', range.apiParams],
    queryFn: () => api.get(withDateRangeQuery('/partner/conversions', range)),
  });

  if (isLoading) {
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="ui-page-title">Конверсии</h1>
          <DateRangeSelector />
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="ui-page-title">Конверсии</h1>
        <DateRangeSelector />
      </div>
      {!data?.items?.length ? (
        <EmptyState
          title="Конверсий пока нет"
          description="Когда клиенты совершат целевые действия по вашим ссылкам, конверсии появятся здесь."
        />
      ) : (
        <div className="ui-card overflow-x-auto">
          <table className="ui-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Оффер</th>
                <th>Order ID</th>
                <th className="text-right">Сумма</th>
                <th className="text-right">Комиссия</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => {
                const status = statusMap[c.status] || statusMap.pending;
                return (
                  <tr key={c.id}>
                    <td className="whitespace-nowrap text-muted-foreground">
                      {new Date(c.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="font-medium">{c.offer_name || c.offer_id}</td>
                    <td className="text-muted-foreground">{c.external_id || '—'}</td>
                    <td className="text-right">{formatMoney(c.amount, c.currency || '₽')}</td>
                    <td className="text-right font-medium">
                      {formatMoney(c.commission_amount, c.currency || '₽')}
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
