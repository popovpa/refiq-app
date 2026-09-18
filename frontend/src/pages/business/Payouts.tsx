import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import { partnerDisplayName } from '@/shared/partners/displayName';
import { formatMoney } from '@/shared/utils/format';
import { OverdueBanner, TestModeBanner } from '@/shared/finance/banners';
import { StatCard } from '@/shared/components/StatCard';
import { Banknote, Clock3, Wallet } from 'lucide-react';
import { useToast } from '@/shared/components/Toast';
import type { FinancialMode } from '@/shared/finance/messages';

interface Payout {
  id: number;
  partner_name?: string | null;
  amount: number;
  currency: string;
  status: string;
  due_at: string | null;
  created_at: string;
  paid_at: string | null;
}

interface PayoutsResponse extends FinancialMode {
  items: Payout[];
  total: number;
  payable_amount: number;
  pending_confirmation: number;
  processing_amount: number;
  overdue_amount: number;
  paid_amount: number;
  partner_traffic_suspended: boolean;
}

const tabs = [
  { key: 'all', label: 'Все' },
  { key: 'awaiting_confirmation', label: 'К подтверждению' },
  { key: 'processing', label: 'В обработке' },
  { key: 'overdue', label: 'Просрочено' },
  { key: 'paid', label: 'Выплачено' },
];

const statusLabels: Record<string, { label: string; className: string }> = {
  created: { label: 'Создана', className: 'bg-yellow-50 text-yellow-700' },
  awaiting_confirmation: { label: 'Ожидает подтверждения', className: 'bg-yellow-50 text-yellow-700' },
  processing: { label: 'В обработке', className: 'bg-blue-50 text-blue-700' },
  paid: { label: 'Выплачено', className: 'bg-accent text-primary' },
  failed: { label: 'Ошибка', className: 'bg-red-50 text-red-700' },
  cancelled: { label: 'Отменено', className: 'bg-red-50 text-red-700' },
  overdue: { label: 'Просрочено', className: 'bg-red-50 text-red-700' },
  manual_review: { label: 'На проверке', className: 'bg-orange-50 text-orange-700' },
};

export function BusinessPayouts() {
  const [activeTab, setActiveTab] = useState('all');
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<PayoutsResponse>({
    queryKey: ['business', 'payouts', activeTab],
    queryFn: () => api.get(`/business/payouts${activeTab !== 'all' ? `?status=${activeTab}` : ''}`),
  });

  const confirm = useMutation({
    mutationFn: (id: number) => api.post(`/business/payouts/${id}/confirm`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business', 'payouts'] });
      addToast('Выплата подтверждена', 'success');
    },
    onError: () => addToast('Не удалось подтвердить выплату', 'error'),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="ui-page-title">Выплаты партнёрам</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          RefIQ считает сумму, а плательщиком является ваш бизнес. Деньги не хранятся в RefIQ.
        </p>
      </div>
      <TestModeBanner visible={data?.financial_mode === 'TEST'} />
      <OverdueBanner visible={data?.partner_traffic_suspended} amount={data?.overdue_amount} />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        <StatCard title="Начислено партнёру" value={formatMoney(data?.payable_amount, '₽')} icon={Wallet} tone="teal" />
        <StatCard title="Ожидает подтверждения" value={formatMoney(data?.pending_confirmation, '₽')} icon={Clock3} tone="orange" />
        <StatCard title="К выплате" value={formatMoney(data?.processing_amount, '₽')} icon={Clock3} tone="blue" />
        <StatCard title="Просрочено" value={formatMoney(data?.overdue_amount, '₽')} icon={Clock3} tone="orange" />
        <StatCard title="Выплачено" value={formatMoney(data?.paid_amount, '₽')} icon={Banknote} tone="purple" />
      </div>

      <div className="flex gap-1 bg-muted rounded-lg p-1 w-fit flex-wrap">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              activeTab === tab.key ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : !data?.items?.length ? (
        <EmptyState
          title="Нет выплат"
          description="Выплаты формируются автоматически каждые 14 дней при сумме от 500 ₽."
        />
      ) : (
        <div className="ui-card overflow-hidden">
          <table className="ui-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Партнёр</th>
                <th className="!text-right">Сумма</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((payout) => {
                const status = statusLabels[payout.status] || statusLabels.awaiting_confirmation;
                const canConfirm = ['created', 'awaiting_confirmation', 'overdue', 'failed', 'manual_review'].includes(
                  payout.status,
                );
                return (
                  <tr key={payout.id}>
                    <td className="text-muted-foreground">{new Date(payout.created_at).toLocaleDateString('ru-RU')}</td>
                    <td className="font-medium">{partnerDisplayName(payout.partner_name)}</td>
                    <td className="text-right font-medium">
                      {formatMoney(payout.amount, payout.currency === 'RUB' ? '₽' : payout.currency)}
                    </td>
                    <td>
                      <span className={cn('ui-badge', status.className)}>{status.label}</span>
                    </td>
                    <td className="text-right">
                      {canConfirm && (
                        <Button size="sm" onClick={() => confirm.mutate(payout.id)} disabled={confirm.isPending}>
                          Подтвердить
                        </Button>
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
