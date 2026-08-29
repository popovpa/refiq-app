import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { cn } from '@/shared/utils/cn';
import { formatMoney } from '@/shared/utils/format';

interface Conversion {
  id: string;
  offer_id: string;
  offer_name?: string | null;
  partner_id: string;
  partner_name?: string | null;
  campaign_name?: string | null;
  click_id: string | null;
  external_id: string | null;
  amount: number;
  currency: string;
  commission_amount: number;
  status: string;
  converted_at: string | null;
  created_at: string;
}

interface ConversionsResponse {
  items: Conversion[];
  total: number;
}

const tabs = [
  { key: 'all', label: 'Все' },
  { key: 'pending', label: 'Ожидание' },
  { key: 'approved', label: 'Одобрены' },
  { key: 'rejected', label: 'Отклонены' },
  { key: 'paid', label: 'Выплачены' },
];

const statusLabels: Record<string, { label: string; className: string }> = {
  pending: { label: 'Ожидание', className: 'bg-yellow-50 text-yellow-700' },
  approved: { label: 'Одобрена', className: 'bg-accent text-primary' },
  rejected: { label: 'Отклонена', className: 'bg-red-50 text-red-700' },
  paid: { label: 'Выплачена', className: 'bg-blue-50 text-blue-700' },
};

export function BusinessConversions() {
  const [activeTab, setActiveTab] = useState('all');
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<ConversionsResponse>({
    queryKey: ['business', 'conversions', activeTab],
    queryFn: () =>
      api.get(
        `/business/conversions${activeTab !== 'all' ? `?status=${activeTab}` : ''}`,
      ),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => api.post(`/business/conversions/${id}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business', 'conversions'] });
      addToast('Конверсия одобрена', 'success');
    },
    onError: () => addToast('Не удалось одобрить', 'error'),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => api.post(`/business/conversions/${id}/reject`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business', 'conversions'] });
      addToast('Конверсия отклонена', 'success');
    },
    onError: () => addToast('Не удалось отклонить', 'error'),
  });

  return (
    <div className="space-y-5">
      <h1 className="ui-page-title">Конверсии</h1>

      <div className="flex gap-1 bg-muted rounded-md p-0.5 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-3 py-1.5 rounded-[7px] text-xs font-semibold transition-colors',
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
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : !data?.items?.length ? (
        <EmptyState
          title="Конверсий пока нет"
          description="Конверсии появятся, когда партнёры начнут приводить клиентов."
        />
      ) : (
        <div className="ui-card overflow-x-auto">
          <table className="ui-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Оффер</th>
                <th>Партнёр</th>
                <th>Кампания</th>
                <th>Order ID</th>
                <th className="text-right">Сумма</th>
                <th className="text-right">Комиссия</th>
                <th>Статус</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((conv) => {
                const status = statusLabels[conv.status] || statusLabels.pending;
                return (
                  <tr key={conv.id}>
                    <td className="whitespace-nowrap text-muted-foreground">
                      {conv.created_at
                        ? new Date(conv.created_at).toLocaleDateString('ru-RU')
                        : '—'}
                    </td>
                    <td className="font-medium">
                      {conv.offer_name || conv.offer_id || '—'}
                    </td>
                    <td>{conv.partner_name || conv.partner_id || '—'}</td>
                    <td className="text-muted-foreground">{conv.campaign_name || '—'}</td>
                    <td className="text-muted-foreground">{conv.external_id || '—'}</td>
                    <td className="text-right">
                      {formatMoney(conv.amount, conv.currency || '₽')}
                    </td>
                    <td className="text-right font-medium">
                      {formatMoney(conv.commission_amount, conv.currency || '₽')}
                    </td>
                    <td>
                      <span className={cn('ui-badge', status.className)}>{status.label}</span>
                    </td>
                    <td className="text-right">
                      {conv.status === 'pending' ? (
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => approveMutation.mutate(conv.id)}
                            disabled={approveMutation.isPending}
                          >
                            Одобрить
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => rejectMutation.mutate(conv.id)}
                            disabled={rejectMutation.isPending}
                          >
                            Отклонить
                          </Button>
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
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
