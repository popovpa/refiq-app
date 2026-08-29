import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ArrowLeftRight, Percent, Tag, Users, Wallet } from 'lucide-react';
import { api } from '@/shared/api/client';
import { EmptyState } from '@/shared/components/EmptyState';
import { Skeleton } from '@/shared/components/Skeleton';
import { StatCard } from '@/shared/components/StatCard';
import { tabClass } from '@/shared/offers/labels';
import { cn } from '@/shared/utils/cn';
import { formatMoney, formatNumber } from '@/shared/utils/format';
import {
  postbackStatusClass,
  postbackStatusLabel,
  sdkStatusLabel,
  type PostbackIntegrationStatus,
  type SdkIntegrationStatus,
} from './settings/types';

interface DashboardData {
  period_days: number;
  kpis: {
    active_offers: number;
    active_partners: number;
    conversions: number;
    conversions_change: number | null;
    sales: number;
    sales_change: number | null;
    cr: number;
    commissions: number;
  };
  timeseries: Array<{ date: string; conversions: number; sales: number }>;
  recent_conversions: Array<{
    id: number | string;
    offer_id: number | string;
    offer_name: string;
    partner_name: string;
    amount: number;
    status: string;
    created_at: string | null;
  }>;
  attention: Array<{ key: string; title: string; detail: string; href: string }>;
  top_offers: Array<{
    id: number | string;
    name: string;
    partners: number;
    conversions: number;
    cr: number;
    sales: number;
  }>;
  top_partners: Array<{
    id: number | string;
    name: string;
    offers: number;
    conversions: number;
    cr: number;
    sales: number;
  }>;
  funnel: {
    clicks: number;
    conversions: number;
    conversion_rate: number;
    approved: number;
    approved_rate: number;
    payout_pending: number;
  };
  integrations: {
    postback: PostbackIntegrationStatus;
    sdk: SdkIntegrationStatus;
  };
}

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  pending: { label: 'Ожидание', className: 'bg-yellow-50 text-yellow-700' },
  approved: { label: 'Одобрена', className: 'bg-accent text-primary' },
  rejected: { label: 'Отклонена', className: 'bg-red-50 text-red-700' },
  paid: { label: 'Выплачена', className: 'bg-blue-50 text-blue-700' },
};

function formatChange(value: number | null): string | undefined {
  if (value === null || value === undefined) return undefined;
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${formatNumber(value)}%`;
}

function formatDay(value: string) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function formatDateTime(value: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatCr(value: number) {
  return `${formatNumber(value)}%`;
}

export function BusinessDashboard() {
  const navigate = useNavigate();
  const [metric, setMetric] = useState<'conversions' | 'sales'>('conversions');
  const { data, isLoading, isError, refetch } = useQuery<DashboardData>({
    queryKey: ['business', 'dashboard', 7],
    queryFn: () => api.get('/business/dashboard?days=7'),
  });

  const chartData = useMemo(
    () =>
      (data?.timeseries || []).map((item) => ({
        ...item,
        label: formatDay(item.date),
        value: metric === 'sales' ? item.sales : item.conversions,
      })),
    [data?.timeseries, metric],
  );
  const hasChartData = chartData.some((item) => item.value > 0);

  if (isLoading) {
    return (
      <div className="flex flex-col flex-1 min-h-0 h-full gap-3 overflow-hidden">
        <h1 className="ui-page-title shrink-0">Обзор</h1>
        <div className="grid grid-cols-2 xl:grid-cols-6 gap-3 shrink-0">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-[88px] rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.7fr)_minmax(240px,0.9fr)] gap-3 flex-1 min-h-0">
          <Skeleton className="rounded-xl min-h-0" />
          <div className="flex flex-col gap-3 min-h-0">
            <Skeleton className="flex-1 rounded-xl min-h-0" />
            <Skeleton className="h-[112px] rounded-xl shrink-0" />
          </div>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 flex-1 min-h-0">
          <Skeleton className="rounded-xl min-h-0" />
          <Skeleton className="rounded-xl min-h-0" />
        </div>
        <div className="flex gap-3 shrink-0">
          <Skeleton className="h-[92px] flex-1 rounded-xl" />
          <Skeleton className="h-[92px] w-[200px] rounded-xl" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-5">
        <h1 className="ui-page-title">Обзор</h1>
        <EmptyState
          title="Не удалось загрузить обзор"
          description="Попробуйте обновить данные. Остальные разделы доступны в меню."
          action={{ label: 'Повторить', onClick: () => refetch() }}
        />
      </div>
    );
  }

  const isEmpty = !data?.kpis.active_offers && !data?.kpis.active_partners && !data?.kpis.conversions;
  if (isEmpty) {
    return (
      <div className="space-y-5">
        <h1 className="ui-page-title">Обзор</h1>
        <EmptyState
          title="Создайте первый оффер"
          description="Опишите продукт, условия партнёрской программы и начните подключать партнёров."
          action={{ label: 'Создать оффер', onClick: () => navigate('/business/offers/new') }}
        />
      </div>
    );
  }

  const kpis = data.kpis;

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full gap-3 max-lg:overflow-auto lg:overflow-hidden">
      <h1 className="ui-page-title shrink-0">Обзор</h1>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 shrink-0">
        <StatCard
          compact
          title="Активные офферы"
          value={formatNumber(kpis.active_offers)}
          icon={Tag}
          tone="purple"
          onClick={() => navigate('/business/offers')}
        />
        <StatCard
          compact
          title="Партнёры"
          value={formatNumber(kpis.active_partners)}
          icon={Users}
          tone="teal"
          onClick={() => navigate('/business/partners')}
        />
        <StatCard
          compact
          title="Конверсии"
          value={formatNumber(kpis.conversions)}
          icon={ArrowLeftRight}
          tone="blue"
          trend={formatChange(kpis.conversions_change)}
          onClick={() => navigate('/business/conversions')}
        />
        <StatCard
          compact
          title="Продажи"
          value={formatMoney(kpis.sales)}
          icon={Wallet}
          tone="orange"
          trend={formatChange(kpis.sales_change)}
          onClick={() => navigate('/business/conversions')}
        />
        <StatCard compact title="CR" value={formatCr(kpis.cr)} icon={Percent} tone="pink" />
        <StatCard compact title="Комиссии партнёрам" value={formatMoney(kpis.commissions)} icon={Wallet} tone="green" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.7fr)_minmax(240px,0.9fr)] gap-3 flex-1 min-h-0">
        <section className="ui-card p-3 min-h-[220px] xl:min-h-0 flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2 shrink-0">
            <h2 className="ui-section-title">{metric === 'sales' ? 'Динамика продаж' : 'Динамика конверсий'}</h2>
            <div className="flex gap-1 bg-muted rounded-md p-0.5" role="tablist" aria-label="Метрика графика">
              <button type="button" role="tab" aria-selected={metric === 'conversions'} className={tabClass(metric === 'conversions')} onClick={() => setMetric('conversions')}>
                Конверсии
              </button>
              <button type="button" role="tab" aria-selected={metric === 'sales'} className={tabClass(metric === 'sales')} onClick={() => setMetric('sales')}>
                Продажи
              </button>
            </div>
          </div>
          <div className="flex-1 min-h-[160px] xl:min-h-0">
            {hasChartData ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="overviewFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(174 72% 40%)" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="hsl(174 72% 40%)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(220 16% 90%)" />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: 'hsl(220 10% 46%)', fontSize: 12 }} />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    width={metric === 'sales' ? 56 : 36}
                    tick={{ fill: 'hsl(220 10% 46%)', fontSize: 12 }}
                    tickFormatter={(value: number) => (metric === 'sales' ? formatNumber(value) : String(value))}
                  />
                  <Tooltip
                    formatter={(value) => {
                      const amount = typeof value === 'number' ? value : Number(value || 0);
                      return metric === 'sales' ? formatMoney(amount) : formatNumber(amount);
                    }}
                    labelFormatter={(_, payload) => formatDay(payload?.[0]?.payload?.date || '')}
                  />
                  <Area type="monotone" dataKey="value" stroke="hsl(174 72% 40%)" strokeWidth={2.5} fill="url(#overviewFill)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-center px-6">
                <p className="text-sm text-muted-foreground">Нет данных за выбранный период.</p>
              </div>
            )}
          </div>
        </section>

        <div className="flex flex-col gap-3 min-h-0">
          <section className="ui-card p-3 flex-1 min-h-0 flex flex-col">
            <div className="flex items-center justify-between gap-3 mb-2 shrink-0">
              <h2 className="ui-section-title">Последние конверсии</h2>
              <button type="button" onClick={() => navigate('/business/conversions')} className="text-xs font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 rounded-sm">
                Все конверсии →
              </button>
            </div>
            {data.recent_conversions.length ? (
              <ul className="space-y-1.5 overflow-auto min-h-0">
                {data.recent_conversions.map((item) => {
                  const status = STATUS_LABELS[item.status] || STATUS_LABELS.pending;
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => navigate('/business/conversions')}
                        className="w-full text-left rounded-md p-1 -mx-1 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{item.offer_name}</p>
                            <p className="text-xs text-muted-foreground truncate">
                              {item.partner_name} · {formatDateTime(item.created_at)}
                            </p>
                          </div>
                          <div className="text-right shrink-0">
                            <p className="text-sm font-semibold">{formatMoney(item.amount)}</p>
                            <span className={cn('ui-badge mt-1', status.className)}>{status.label}</span>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground py-4 text-center">Конверсий за выбранный период пока нет.</p>
            )}
          </section>

          <section className="ui-card p-3 shrink-0 max-h-[148px] overflow-auto">
            <h2 className="ui-section-title mb-2">Требует внимания</h2>
            {data.attention.length ? (
              <ul className="space-y-1.5">
                {data.attention.map((item) => (
                  <li key={item.key}>
                    <button
                      type="button"
                      onClick={() => navigate(item.href)}
                      className="w-full text-left rounded-md p-1 -mx-1 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                    >
                      <p className="text-sm font-medium">{item.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{item.detail}</p>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div>
                <p className="text-sm font-medium">Всё в порядке</p>
                <p className="text-xs text-muted-foreground mt-1">Нет элементов, требующих внимания.</p>
              </div>
            )}
          </section>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 flex-1 min-h-0">
        <RankTable
          title="Топ офферов"
          emptyTitle="Недостаточно данных"
          emptyText="Рейтинг появится после первых конверсий."
          linkLabel="Все офферы →"
          onLink={() => navigate('/business/offers')}
          columns={['Оффер', 'Партнёры', 'Конверсии', 'CR', 'Продажи']}
          rows={data.top_offers.map((item) => ({
            id: item.id,
            cells: [item.name, formatNumber(item.partners), formatNumber(item.conversions), formatCr(item.cr), formatMoney(item.sales)],
            hideOnMobile: [false, true, false, true, false],
            onOpen: () => navigate(`/business/offers/${item.id}`),
          }))}
        />
        <RankTable
          title="Эффективность партнёров"
          emptyTitle="Недостаточно данных"
          emptyText="Статистика появится после начала партнёрского трафика."
          linkLabel="Все партнёры →"
          onLink={() => navigate('/business/partners')}
          columns={['Партнёр', 'Офферы', 'Конверсии', 'CR', 'Продажи']}
          rows={data.top_partners.map((item) => ({
            id: item.id,
            cells: [item.name, formatNumber(item.offers), formatNumber(item.conversions), formatCr(item.cr), formatMoney(item.sales)],
            hideOnMobile: [false, true, false, true, false],
            onOpen: () => navigate('/business/partners'),
          }))}
        />
      </div>

      <div className="flex flex-col xl:flex-row gap-3 shrink-0">
        <section className="ui-card p-3 flex-1 min-w-0">
          <h2 className="ui-section-title mb-2">Воронка</h2>
          <div className="flex flex-col sm:flex-row sm:items-stretch gap-2 sm:gap-1.5">
            <FunnelStep label="Клики" value={formatNumber(data.funnel.clicks)} />
            <FunnelArrow />
            <FunnelStep label="Конверсии" value={formatNumber(data.funnel.conversions)} hint={`CR ${formatCr(data.funnel.conversion_rate)}`} />
            <FunnelArrow />
            <FunnelStep label="Подтверждено" value={formatNumber(data.funnel.approved)} hint={`${formatCr(data.funnel.approved_rate)}`} />
            <FunnelArrow />
            <FunnelStep label="К выплате" value={formatMoney(data.funnel.payout_pending)} />
          </div>
        </section>

        <section className="ui-card p-3 w-full xl:w-max xl:max-w-[13.5rem] shrink-0">
          <div className="flex items-center justify-between gap-2 mb-2">
            <h2 className="ui-section-title">Интеграции</h2>
            <button
              type="button"
              onClick={() => navigate('/business/settings')}
              className="text-xs font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 rounded-sm whitespace-nowrap"
            >
              Настройки
            </button>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium whitespace-nowrap">Postback / S2S</p>
              <span className={cn('ui-badge', postbackStatusClass(data.integrations.postback))}>
                {postbackStatusLabel(data.integrations.postback)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-medium whitespace-nowrap">JavaScript SDK</p>
              <span className={cn('ui-badge', postbackStatusClass(data.integrations.sdk))}>
                {sdkStatusLabel(data.integrations.sdk)}
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function FunnelStep({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-muted/30 px-2.5 py-1.5 min-w-0 flex-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold mt-0.5 truncate">{value}</p>
      {hint && <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>}
    </div>
  );
}

function FunnelArrow() {
  return (
    <div className="hidden sm:flex items-center justify-center text-muted-foreground shrink-0 px-0.5" aria-hidden>
      →
    </div>
  );
}

function RankTable({
  title,
  emptyTitle,
  emptyText,
  linkLabel,
  onLink,
  columns,
  rows,
}: {
  title: string;
  emptyTitle: string;
  emptyText: string;
  linkLabel: string;
  onLink: () => void;
  columns: string[];
  rows: Array<{ id: number | string; cells: string[]; hideOnMobile?: boolean[]; onOpen: () => void }>;
}) {
  return (
    <section className="ui-card overflow-hidden min-h-0 flex flex-col">
      <div className="flex items-center justify-between gap-3 px-3 py-2 shrink-0">
        <h2 className="ui-section-title">{title}</h2>
        <button
          type="button"
          onClick={onLink}
          className="text-xs font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 rounded-sm"
        >
          {linkLabel}
        </button>
      </div>
      {rows.length ? (
        <div className="flex-1 min-h-0 overflow-auto">
          <table className="ui-table [&_th]:px-3 [&_th]:py-2 [&_td]:px-3 [&_td]:py-2">
            <thead>
              <tr>
                {columns.map((column, index) => (
                  <th
                    key={column}
                    className={cn(
                      index === 0 ? '' : 'text-right',
                      rows[0]?.hideOnMobile?.[index] ? 'hidden sm:table-cell' : '',
                    )}
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.id}
                  tabIndex={0}
                  role="link"
                  aria-label={row.cells[0]}
                  className="cursor-pointer focus-visible:outline-none focus-visible:bg-muted/60"
                  onClick={row.onOpen}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      row.onOpen();
                    }
                  }}
                >
                  {row.cells.map((cell, index) => (
                    <td
                      key={`${row.id}-${index}`}
                      className={cn(
                        index === 0 ? 'font-medium max-w-[160px] truncate' : 'text-right tabular-nums',
                        row.hideOnMobile?.[index] ? 'hidden sm:table-cell' : '',
                      )}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-3 pb-3 pt-1 flex-1">
          <p className="text-sm font-medium">{emptyTitle}</p>
          <p className="text-sm text-muted-foreground mt-1">{emptyText}</p>
        </div>
      )}
    </section>
  );
}
