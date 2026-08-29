import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { cn } from '@/shared/utils/cn';
import { formatMoney, formatNumber } from '@/shared/utils/format';

interface Partner {
  id: string;
  display_name: string;
  email?: string | null;
  status: string;
  offers_count?: number | null;
  total_conversions?: number | null;
  total_earned?: number | null;
  joined_at?: string | null;
}

interface PartnersResponse {
  items: Partner[];
  total: number;
}

const tabs = [
  { key: 'all', label: 'Все' },
  { key: 'active', label: 'Активные' },
  { key: 'pending', label: 'Ожидающие' },
  { key: 'blocked', label: 'Заблокированные' },
];

const statusLabels: Record<string, { label: string; className: string }> = {
  active: { label: 'Активен', className: 'bg-accent text-primary' },
  pending: { label: 'Ожидает', className: 'bg-yellow-50 text-yellow-700' },
  blocked: { label: 'Заблокирован', className: 'bg-red-50 text-red-700' },
};

export function BusinessPartners() {
  const [activeTab, setActiveTab] = useState('all');

  const { data, isLoading, isError } = useQuery<PartnersResponse>({
    queryKey: ['business', 'partners', activeTab],
    queryFn: () => api.get(`/business/partners${activeTab !== 'all' ? `?status=${activeTab}` : ''}`),
  });

  return (
    <div className="space-y-5">
      <h1 className="ui-page-title">Партнёры</h1>

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
      ) : isError ? (
        <EmptyState
          title="Не удалось загрузить партнёров"
          description="Попробуйте обновить страницу или повторить позже."
        />
      ) : !data?.items?.length ? (
        <EmptyState
          title="Нет партнёров"
          description="Партнёры появятся, когда начнут подключаться к вашим офферам."
        />
      ) : (
        <div className="ui-card overflow-hidden">
          <table className="ui-table">
            <thead>
              <tr>
                <th>Партнёр</th>
                <th>Статус</th>
                <th className="!text-right">Офферы</th>
                <th className="!text-right">Конверсии</th>
                <th className="!text-right">Заработано</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((partner) => {
                const status = statusLabels[partner.status] || statusLabels.active;
                return (
                  <tr key={partner.id}>
                    <td>
                      <p className="font-medium">{partner.display_name}</p>
                      <p className="text-xs text-muted-foreground">{partner.email}</p>
                    </td>
                    <td>
                      <span className={cn('ui-badge', status.className)}>
                        {status.label}
                      </span>
                    </td>
                    <td className="text-right">{formatNumber(partner.offers_count)}</td>
                    <td className="text-right">{formatNumber(partner.total_conversions)}</td>
                    <td className="text-right font-medium">{formatMoney(partner.total_earned)}</td>
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
