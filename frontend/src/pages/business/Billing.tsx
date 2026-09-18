import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CreditCard } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { StatCard } from '@/shared/components/StatCard';
import { Button } from '@/shared/components/Button';
import { EmptyState } from '@/shared/components/EmptyState';
import { formatMoney } from '@/shared/utils/format';
import { TestModeBanner } from '@/shared/finance/banners';
import type { FinancialMode } from '@/shared/finance/messages';
import { useToast } from '@/shared/components/Toast';

interface SubscriptionResponse extends FinancialMode {
  subscription: {
    plan_name: string;
    status: string;
    trial_ends_at: string | null;
    next_billing_date: string | null;
    grace_ends_at: string | null;
    amount: number;
    currency: string;
  };
}

interface HistoryResponse extends FinancialMode {
  invoices: Array<{
    id: number;
    amount: number;
    currency: string;
    status: string;
    period_start: string;
    period_end: string;
    due_at: string;
    paid_at: string | null;
  }>;
}

const statusLabel: Record<string, string> = {
  trial: 'Пробный период',
  active: 'Активна',
  past_due: 'Просрочена',
  suspended: 'Приостановлена',
  cancelled: 'Отменена',
  open: 'К оплате',
  paid: 'Оплачен',
};

export function BusinessBilling() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const { data: subData, isLoading: subLoading } = useQuery<SubscriptionResponse>({
    queryKey: ['business', 'subscription'],
    queryFn: () => api.get('/business/subscription'),
  });
  const { data: history, isLoading: histLoading } = useQuery<HistoryResponse>({
    queryKey: ['business', 'billing-history'],
    queryFn: () => api.get('/business/billing-history'),
  });
  const pay = useMutation({
    mutationFn: (invoiceId: number) => api.post(`/business/invoices/${invoiceId}/pay`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business', 'billing-history'] });
      queryClient.invalidateQueries({ queryKey: ['business', 'subscription'] });
      addToast('Счёт отправлен в оплату', 'success');
    },
    onError: () => addToast('Не удалось создать платёж', 'error'),
  });

  if (subLoading || histLoading) {
    return (
      <div className="space-y-5">
        <h1 className="ui-page-title">Тариф и счета</h1>
        <Skeleton className="h-28 rounded-xl" />
      </div>
    );
  }

  const sub = subData?.subscription;
  const testMode = subData?.financial_mode === 'TEST' || history?.financial_mode === 'TEST';

  return (
    <div className="space-y-5">
      <div>
        <h1 className="ui-page-title">Тариф и счета</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">Оплата RefIQ отдельно от выплат партнёрам.</p>
      </div>
      <TestModeBanner visible={testMode} />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard title="Тариф" value={sub?.plan_name || 'Pro'} icon={CreditCard} tone="purple" />
        <StatCard title="Статус" value={statusLabel[sub?.status || ''] || sub?.status || '—'} icon={CreditCard} tone="teal" />
        <StatCard
          title="Конец trial"
          value={sub?.trial_ends_at ? new Date(sub.trial_ends_at).toLocaleDateString('ru-RU') : '—'}
          icon={CreditCard}
          tone="blue"
        />
        <StatCard
          title="Следующее списание"
          value={sub?.next_billing_date ? new Date(sub.next_billing_date).toLocaleDateString('ru-RU') : '—'}
          icon={CreditCard}
          tone="orange"
        />
      </div>
      {sub?.status === 'past_due' && (
        <div className="rounded-lg border border-destructive/30 bg-red-50 px-4 py-3 text-sm text-destructive">
          Есть задолженность перед RefIQ. Кабинет и выплаты партнёрам доступны, тариф будет приостановлен после льготного периода.
        </div>
      )}
      <div className="ui-card overflow-x-auto">
        <table className="ui-table">
          <thead>
            <tr>
              <th>Период</th>
              <th className="text-right">Сумма</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(history?.invoices || []).map((invoice) => (
              <tr key={invoice.id}>
                <td className="text-muted-foreground">
                  {new Date(invoice.period_start).toLocaleDateString('ru-RU')} — {new Date(invoice.period_end).toLocaleDateString('ru-RU')}
                </td>
                <td className="text-right font-medium">{formatMoney(invoice.amount, '₽')}</td>
                <td>{statusLabel[invoice.status] || invoice.status}</td>
                <td className="text-right">
                  {invoice.status !== 'paid' && (
                    <Button size="sm" onClick={() => pay.mutate(invoice.id)} disabled={pay.isPending}>
                      Оплатить
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!history?.invoices?.length && (
          <div className="p-4">
            <EmptyState title="Счетов пока нет" description="Счета появятся после окончания пробного периода." />
          </div>
        )}
      </div>
    </div>
  );
}
