import { Link, useNavigate } from 'react-router-dom';
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
import {
  Wallet,
  Clock3,
  ArrowLeftRight,
  MousePointerClick,
  Percent,
  Link2,
  Tag,
  Banknote,
  ArrowUpRight,
} from 'lucide-react';
import { api } from '@/shared/api/client';
import { StatCard } from '@/shared/components/StatCard';
import { Skeleton } from '@/shared/components/Skeleton';
import { Button } from '@/shared/components/Button';
import { EmptyState } from '@/shared/components/EmptyState';
import { formatMoney, formatNumber } from '@/shared/utils/format';
import { PageHeading } from '@/shared/dateRange/PageHeading';
import { useDateRange, withDateRangeQuery } from '@/shared/dateRange';
import { OfferImage } from '@/shared/offers/OfferImage';

interface PartnerDashboardData {
  active_offers: number;
  active_links: number;
  has_offers?: boolean;
  total_conversions: number;
  total_earnings: number;
  pending_payout: number;
}

interface OfferItem {
  id: string;
  name: string;
  description?: string | null;
  image_url?: string | null;
  conversion_type?: string;
  partner_status?: string | null;
  status?: string;
  commission_rules?: Array<{ type: string; value: number; currency: string | null }>;
}

const chartData = [
  { day: '12 мая', value: 4200 },
  { day: '13 мая', value: 6100 },
  { day: '14 мая', value: 5800 },
  { day: '15 мая', value: 9200 },
  { day: '16 мая', value: 8700 },
  { day: '17 мая', value: 12400 },
  { day: '18 мая', value: 11100 },
];

function formatRule(offer: OfferItem): string {
  const rule = offer.commission_rules?.[0];
  if (!rule) return '—';
  if (rule.type === 'percent') return `CPA • ${rule.value}%`;
  return `CPA • ${formatNumber(rule.value)} ${rule.currency || '₽'}`;
}

export function PartnerDashboard() {
  const navigate = useNavigate();
  const range = useDateRange();

  const { data, isLoading } = useQuery<PartnerDashboardData>({
    queryKey: ['partner', 'dashboard', range.apiParams],
    queryFn: () => api.get(withDateRangeQuery('/partner/dashboard', range)),
  });

  const { data: myOffers } = useQuery<{ items: OfferItem[] }>({
    queryKey: ['partner', 'offers', 'my'],
    queryFn: () => api.get('/partner/offers'),
  });

  const { data: marketplace } = useQuery<{ items: OfferItem[] }>({
    queryKey: ['partner', 'offers', 'marketplace'],
    queryFn: () => api.get('/partner/offers/marketplace'),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeading title="Обзор" dateRangeFilter="header" />
        <div className="grid grid-cols-2 xl:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-72 rounded-xl" />
      </div>
    );
  }

  const isOnboarding = data ? data.has_offers === false && !data.active_offers : false;

  if (isOnboarding) {
    return (
      <div className="space-y-5">
        <PageHeading title="Обзор" dateRangeFilter="none" />
        <EmptyState
          title="Найдите первый оффер для продвижения"
          description="Откройте каталог, выберите оффер и получите партнёрскую ссылку."
          action={{ label: 'Открыть офферы', onClick: () => navigate('/partner/offers') }}
        />
      </div>
    );
  }

  const cr =
    data && data.total_conversions > 0 && data.active_links > 0
      ? ((data.total_conversions / Math.max(data.active_links * 20, 1)) * 100).toFixed(1)
      : '0.0';

  const stats = [
    {
      title: 'Заработано',
      value: formatMoney(data?.total_earnings, '₽'),
      icon: Wallet,
      tone: 'purple' as const,
      trend: '↑ 12,4%',
    },
    {
      title: 'В ожидании',
      value: formatMoney(data?.pending_payout, '₽'),
      icon: Clock3,
      tone: 'orange' as const,
      trend: '↑ 4,1%',
    },
    {
      title: 'Конверсии',
      value: formatNumber(data?.total_conversions),
      icon: ArrowLeftRight,
      tone: 'blue' as const,
      trend: '↑ 9,8%',
    },
    {
      title: 'Мои ссылки',
      value: formatNumber(data?.active_links),
      icon: MousePointerClick,
      tone: 'teal' as const,
      trend: '↑ 6,2%',
    },
    {
      title: 'CR',
      value: `${cr}%`,
      icon: Percent,
      tone: 'pink' as const,
      trend: '↑ 1,3%',
    },
  ];

  const quickLinks = [
    {
      title: 'Создать ссылку',
      description: 'Новая tracking-ссылка для оффера',
      icon: Link2,
      tone: 'bg-brand-soft text-brand',
      to: '/partner/links',
    },
    {
      title: 'Офферы',
      description: 'Каталог и подключённые офферы',
      icon: Tag,
      tone: 'bg-orange-50 text-warning',
      to: '/partner/offers',
    },
    {
      title: 'Конверсии',
      description: 'Статусы и комиссии',
      icon: ArrowLeftRight,
      tone: 'bg-blue-50 text-info',
      to: '/partner/conversions',
    },
    {
      title: 'Выплаты',
      description: 'Доступно к выводу',
      icon: Banknote,
      tone: 'bg-accent text-primary',
      to: '/partner/payouts',
    },
  ];

  const activeOffers = (myOffers?.items || []).filter(
    (o) => o.status === 'approved' || o.partner_status === 'approved',
  );
  const recommended = (marketplace?.items || [])
    .filter((o) => o.partner_status !== 'approved')
    .slice(0, 4);

  return (
    <div className="space-y-5">
      <PageHeading title="Обзор" dateRangeFilter="header" />
      <div className="grid grid-cols-2 xl:grid-cols-5 gap-3">
        {stats.map((stat) => (
          <StatCard
            key={stat.title}
            title={stat.title}
            value={stat.value}
            icon={stat.icon}
            tone={stat.tone}
            trend={stat.trend}
            trendLabel="vs прошлый период"
          />
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="ui-card p-5 xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="ui-section-title">Динамика заработка</h2>
            <select className="h-8 px-2 rounded-md border bg-card text-xs text-muted-foreground">
              <option>По дням</option>
              <option>По неделям</option>
            </select>
          </div>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="earnFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="hsl(248 78% 62%)" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="hsl(248 78% 62%)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(220 16% 90%)" />
                <XAxis
                  dataKey="day"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'hsl(220 10% 46%)', fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'hsl(220 10% 46%)', fontSize: 12 }}
                  tickFormatter={(v) => `${Math.round(v / 1000)}k`}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    border: '1px solid hsl(220 16% 90%)',
                    boxShadow: '0 8px 24px rgba(16,24,40,0.08)',
                  }}
                  formatter={(value) => [`${Number(value ?? 0).toLocaleString('ru-RU')} ₽`, 'Заработок']}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="hsl(248 78% 62%)"
                  strokeWidth={2.5}
                  fill="url(#earnFill)"
                  dot={{ r: 4, fill: '#fff', stroke: 'hsl(248 78% 62%)', strokeWidth: 2 }}
                  activeDot={{ r: 5 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="ui-card p-5">
          <h2 className="ui-section-title mb-4">Быстрые ссылки</h2>
          <div className="space-y-2">
            {quickLinks.map((item) => (
              <button
                key={item.title}
                type="button"
                onClick={() => navigate(item.to)}
                className="w-full flex items-center gap-3 rounded-lg p-3 text-left hover:bg-muted/60 transition-colors"
              >
                <div className={`w-9 h-9 rounded-md flex items-center justify-center ${item.tone}`}>
                  <item.icon size={16} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground truncate">{item.description}</p>
                </div>
                <ArrowUpRight size={14} className="text-muted-foreground" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="ui-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="ui-section-title">Мои активные офферы</h2>
            <Link to="/partner/offers?tab=my" className="text-xs font-medium text-primary hover:underline inline-flex items-center gap-1">
              Смотреть все <ArrowUpRight size={12} />
            </Link>
          </div>
          {activeOffers.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Пока нет активных офферов</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="ui-table">
                <thead>
                  <tr>
                    <th>Оффер</th>
                    <th>Модель</th>
                    <th className="text-right">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {activeOffers.slice(0, 5).map((offer) => (
                    <tr key={offer.id}>
                      <td>
                        <Link to={`/partner/offers/${offer.id}`} className="flex items-center gap-3 min-w-0 group">
                          <OfferImage src={offer.image_url} name={offer.name} size="sm" />
                          <div className="min-w-0">
                            <p className="font-medium group-hover:text-primary">{offer.name}</p>
                            <p className="text-xs text-muted-foreground">{offer.conversion_type || 'sale'}</p>
                          </div>
                        </Link>
                      </td>
                      <td className="text-muted-foreground">{formatRule(offer)}</td>
                      <td className="text-right">
                        <span className="ui-badge bg-accent text-primary">Активен</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pt-4 text-center">
            <Link to="/partner/offers?tab=my" className="text-sm font-medium text-primary hover:underline">
              Смотреть все офферы →
            </Link>
          </div>
        </div>

        <div className="ui-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="ui-section-title">Рекомендуемые офферы</h2>
            <Link to="/partner/offers" className="text-xs font-medium text-primary hover:underline inline-flex items-center gap-1">
              Смотреть все <ArrowUpRight size={12} />
            </Link>
          </div>
          {recommended.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Нет рекомендаций</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="ui-table">
                <thead>
                  <tr>
                    <th>Оффер</th>
                    <th>Модель</th>
                    <th className="text-right">Действие</th>
                  </tr>
                </thead>
                <tbody>
                  {recommended.map((offer) => (
                    <tr key={offer.id}>
                      <td>
                        <Link to={`/partner/offers/${offer.id}`} className="flex items-center gap-3 min-w-0 group">
                          <OfferImage src={offer.image_url} name={offer.name} size="sm" />
                          <div className="min-w-0">
                            <p className="font-medium group-hover:text-primary">{offer.name}</p>
                            <p className="text-xs text-muted-foreground line-clamp-1">
                              {offer.description || offer.conversion_type || 'Оффер'}
                            </p>
                          </div>
                        </Link>
                      </td>
                      <td className="text-muted-foreground">{formatRule(offer)}</td>
                      <td className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/partner/offers/${offer.id}`)}
                        >
                          Подключить
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="pt-4 text-center">
            <Link to="/partner/offers" className="text-sm font-medium text-primary hover:underline">
              Смотреть все офферы →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
