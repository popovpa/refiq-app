import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatMoney, formatNumber } from '@/shared/utils/format';
import type { BusinessOfferDetailData } from './offerDetailTypes';

type AttentionTarget = 'partners' | 'partners-pending' | 'promotion';

type AttentionItem = {
  key: string;
  title: string;
  target?: AttentionTarget;
};

function isActiveLink(status?: string | null) {
  return (status || '').toLowerCase() === 'active';
}

function cr(clicks: number, conversions: number) {
  if (clicks <= 0) return null;
  return Math.round((conversions / clicks) * 1000) / 10;
}

function pctChange(current: number, previous: number) {
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 1000) / 10;
}

function formatPct(value: number | null | undefined, fallback = '—') {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return `${formatNumber(value)}%`;
}

function formatSignedPct(value: number) {
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${formatNumber(value)}%`;
}

function formatSignedPp(value: number) {
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${formatNumber(value)} п.п.`;
}

function formatDay(value: string) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function seriesWindow(
  series: BusinessOfferDetailData['timeseries'],
  start: number,
  end?: number,
) {
  return series.slice(start, end).reduce(
    (acc, item) => ({
      clicks: acc.clicks + (item.clicks || 0),
      conversions: acc.conversions + (item.conversions || 0),
    }),
    { clicks: 0, conversions: 0 },
  );
}

function ruCount(n: number, one: string, few: string, many: string) {
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (last === 1) return one;
  if (last >= 2 && last <= 4) return few;
  return many;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm leading-8">
      <span className="text-muted-foreground truncate">{label}</span>
      <span className="font-medium tabular-nums shrink-0">{value}</span>
    </div>
  );
}

export function offerKpiTrends(timeseries: BusinessOfferDetailData['timeseries']) {
  if (timeseries.length < 14) {
    return { clicks: undefined as string | undefined, conversions: undefined as string | undefined, cr: undefined as string | undefined };
  }
  const recent = seriesWindow(timeseries, -7);
  const previous = seriesWindow(timeseries, -14, -7);
  const clicksTrend = pctChange(recent.clicks, previous.clicks);
  const conversionsTrend = pctChange(recent.conversions, previous.conversions);
  const recentCr = cr(recent.clicks, recent.conversions);
  const previousCr = cr(previous.clicks, previous.conversions);
  const crTrend =
    recentCr === null || previousCr === null ? null : Math.round((recentCr - previousCr) * 10) / 10;
  return {
    clicks: clicksTrend ? formatSignedPct(clicksTrend) : undefined,
    conversions: conversionsTrend ? formatSignedPct(conversionsTrend) : undefined,
    cr: crTrend ? formatSignedPp(crTrend) : undefined,
  };
}

export function OfferOverview({
  offer,
  ownLinks = [],
  onOpenPartners,
  onOpenPromotion,
}: {
  offer: BusinessOfferDetailData;
  ownLinks?: Array<{ status: string; clicks?: number }>;
  onOpenPartners: (filter?: 'all' | 'approved' | 'pending') => void;
  onOpenPromotion: () => void;
}) {
  const approvedConversions = offer.kpis.approved_conversions;
  const revenue = offer.kpis.revenue || 0;
  const commissions = offer.kpis.commissions || 0;
  const convertingPartners = offer.partners.filter((row) => row.status === 'approved' && row.conversions > 0).length;
  const averageOrderValue =
    approvedConversions && approvedConversions > 0 ? revenue / approvedConversions : null;
  const commissionShare = revenue > 0 ? Math.round((commissions / revenue) * 1000) / 10 : null;
  const afterCommissions = revenue - commissions;
  const clickToConv = cr(offer.kpis.clicks, offer.kpis.conversions);
  const convToApproved =
    offer.kpis.conversions > 0 && approvedConversions !== undefined
      ? Math.round((approvedConversions / offer.kpis.conversions) * 1000) / 10
      : null;
  const hasChartData = offer.timeseries.some((item) => item.clicks > 0 || item.conversions > 0);
  const chartData = offer.timeseries.map((item) => ({ ...item, label: formatDay(item.date) }));
  const activePartnerLinks = offer.promotion_links.filter((link) => isActiveLink(link.status));
  const activeOwnLinks = ownLinks.filter((link) => isActiveLink(link.status));
  const activeLinks = [...activePartnerLinks, ...activeOwnLinks];
  const linksWithClicks = activeLinks.filter((link) => (link.clicks || 0) > 0).length;
  const linksWithoutClicks = activeLinks.filter((link) => (link.clicks || 0) === 0).length;
  const pendingCount = offer.pending_applications.length;
  const topPartners = offer.top_partners.slice(0, 5);
  const crTrend = offerKpiTrends(offer.timeseries).cr;
  const crDropped =
    crTrend && crTrend.trim().startsWith('-')
      ? Number(crTrend.replace('+', '').replace(' п.п.', '').replace(',', '.'))
      : 0;

  const attention: AttentionItem[] = [];
  if (pendingCount > 0) {
    attention.push({
      key: 'pending',
      title: `${pendingCount} ${ruCount(pendingCount, 'заявка', 'заявки', 'заявок')} партнёров ожидают решения`,
      target: 'partners-pending',
    });
  }
  if (linksWithoutClicks > 0) {
    attention.push({
      key: 'idle-links',
      title: `${linksWithoutClicks} ${ruCount(
        linksWithoutClicks,
        'активная ссылка',
        'активные ссылки',
        'активных ссылок',
      )} без кликов`,
      target: 'promotion',
    });
  }
  if (crDropped < 0) {
    attention.push({
      key: 'cr-drop',
      title: `CR снизился на ${formatNumber(Math.abs(crDropped))} п.п.`,
    });
  }
  const attentionItems = attention.slice(0, 3);

  const openAttention = (item: AttentionItem) => {
    if (item.target === 'partners-pending') onOpenPartners('pending');
    else if (item.target === 'partners') onOpenPartners('approved');
    else if (item.target === 'promotion') onOpenPromotion();
  };

  return (
    <div className="grid gap-3 xl:grid-rows-[minmax(230px,1fr)_minmax(180px,0.82fr)] min-h-0">
      <div className="grid gap-3 min-h-0 xl:grid-cols-[minmax(0,1.95fr)_minmax(260px,1fr)]">
        <section className="ui-card p-4 min-h-[230px] flex flex-col">
          <h2 className="ui-section-title mb-2">Динамика кликов и конверсий</h2>
          <div className="flex-1 min-h-[198px]">
            {hasChartData ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="offerClicksFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(248 78% 62%)" stopOpacity={0.22} />
                      <stop offset="100%" stopColor="hsl(248 78% 62%)" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="offerConversionsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(174 72% 40%)" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="hsl(174 72% 40%)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(220 16% 90%)" />
                  <XAxis
                    dataKey="label"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'hsl(220 10% 46%)', fontSize: 11 }}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    width={32}
                    allowDecimals={false}
                    tick={{ fill: 'hsl(220 10% 46%)', fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(value, name) => [
                      formatNumber(typeof value === 'number' ? value : Number(value || 0)),
                      name === 'clicks' ? 'Клики' : 'Конверсии',
                    ]}
                    labelFormatter={(_, payload) => formatDay(payload?.[0]?.payload?.date || '')}
                  />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
                    formatter={(value) => (value === 'clicks' ? 'Клики' : 'Конверсии')}
                  />
                  <Area
                    type="monotone"
                    dataKey="clicks"
                    name="clicks"
                    stroke="hsl(248 78% 62%)"
                    strokeWidth={2}
                    fill="url(#offerClicksFill)"
                  />
                  <Area
                    type="monotone"
                    dataKey="conversions"
                    name="conversions"
                    stroke="hsl(174 72% 40%)"
                    strokeWidth={2}
                    fill="url(#offerConversionsFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-center px-4">
                <p className="text-sm text-muted-foreground">Пока недостаточно данных для построения динамики.</p>
              </div>
            )}
          </div>
        </section>

        <section className="ui-card p-4 flex flex-col min-h-0">
          <h2 className="ui-section-title mb-1">Эффективность</h2>
          <div>
            <MetricRow label="Активных партнёров" value={formatNumber(offer.active_partners)} />
            <MetricRow label="Партнёров с конверсией" value={formatNumber(convertingPartners)} />
            <MetricRow
              label="Средний чек"
              value={averageOrderValue === null ? '—' : formatMoney(Math.round(averageOrderValue))}
            />
            {commissionShare !== null && <MetricRow label="Доля комиссий" value={formatPct(commissionShare)} />}
          </div>
          <div className="mt-3 pt-3 border-t border-border/70 flex-1 min-h-0">
            <h3 className="text-xs font-semibold text-foreground mb-2">Воронка</h3>
            {offer.kpis.clicks === 0 && offer.kpis.conversions === 0 ? (
              <p className="text-sm text-muted-foreground">Пока недостаточно данных.</p>
            ) : (
              <div className="flex items-stretch gap-2 text-center">
                <FunnelStep label="Клики" value={formatNumber(offer.kpis.clicks)} />
                <FunnelRate value={formatPct(clickToConv)} />
                <FunnelStep label="Конверсии" value={formatNumber(offer.kpis.conversions)} />
                <FunnelRate value={formatPct(convToApproved)} />
                <FunnelStep label="Подтверждено" value={formatNumber(approvedConversions)} />
              </div>
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-3 min-h-0 sm:grid-cols-2 xl:grid-cols-4">
        <section className="ui-card p-4 flex flex-col min-h-0">
          <div className="flex items-center justify-between gap-3 mb-2">
            <h2 className="ui-section-title">Лучшие партнёры</h2>
            <button
              type="button"
              onClick={() => onOpenPartners('approved')}
              className="text-xs font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 rounded-sm"
            >
              Все партнёры →
            </button>
          </div>
          {topPartners.length ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground">
                  <th className="text-left font-medium pb-1">Партнёр</th>
                  <th className="text-right font-medium pb-1">Конв.</th>
                  <th className="text-right font-medium pb-1 hidden sm:table-cell">CR</th>
                  <th className="text-right font-medium pb-1">Продажи</th>
                </tr>
              </thead>
              <tbody>
                {topPartners.map((row) => (
                  <tr
                    key={row.id}
                    tabIndex={0}
                    aria-label={`${row.name}, ${formatNumber(row.conversions)} конверсий, CR ${formatPct(row.cr)}, продажи ${formatMoney(row.revenue)}`}
                    className="cursor-pointer rounded-sm hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                    onClick={() => onOpenPartners('approved')}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        onOpenPartners('approved');
                      }
                    }}
                  >
                    <td className="h-8 font-medium max-w-[140px] truncate">{row.name}</td>
                    <td className="h-8 text-right tabular-nums">{formatNumber(row.conversions)}</td>
                    <td className="h-8 text-right tabular-nums text-muted-foreground hidden sm:table-cell">
                      {formatPct(row.cr)}
                    </td>
                    <td className="h-8 text-right tabular-nums">{formatMoney(row.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-muted-foreground">Первые показатели появятся после начала продвижения.</p>
          )}
        </section>

        <section className="ui-card p-4 flex flex-col min-h-0">
          <h2 className="ui-section-title mb-1">Экономика</h2>
          <MetricRow label="Выручка" value={formatMoney(revenue)} />
          <MetricRow label="Комиссии партнёрам" value={formatMoney(commissions)} />
          <MetricRow label="Доля комиссий" value={formatPct(commissionShare)} />
          <div className="flex items-baseline justify-between gap-3 text-sm leading-8">
            <span
              className="text-muted-foreground truncate underline decoration-dotted underline-offset-2"
              title="Выручка после партнёрских комиссий. Другие расходы бизнеса не учитываются."
              aria-label="Выручка после партнёрских комиссий. Другие расходы бизнеса не учитываются."
            >
              После комиссий
            </span>
            <span className="font-medium tabular-nums shrink-0">{formatMoney(afterCommissions)}</span>
          </div>
        </section>

        <section className="ui-card p-4 flex flex-col min-h-0">
          <h2 className="ui-section-title mb-1">Продвижение</h2>
          <MetricRow label="Активные партнёры" value={formatNumber(offer.active_partners)} />
          <MetricRow label="Активные ссылки" value={formatNumber(offer.active_links)} />
          {offer.traffic_split && (
            <>
              <MetricRow label="Свои клики" value={formatNumber(offer.traffic_split.own.clicks)} />
              <MetricRow label="Партнёрские клики" value={formatNumber(offer.traffic_split.partner.clicks)} />
            </>
          )}
          <MetricRow label="Ссылки с кликами" value={formatNumber(linksWithClicks)} />
          <MetricRow label="Ссылки без кликов" value={formatNumber(linksWithoutClicks)} />
        </section>

        <section className="ui-card p-4 flex flex-col min-h-0">
          <h2 className="ui-section-title mb-2">Требует внимания</h2>
          {attentionItems.length ? (
            <ul className="space-y-0.5">
              {attentionItems.map((item) => (
                <li key={item.key}>
                  {item.target ? (
                    <button
                      type="button"
                      onClick={() => openAttention(item)}
                      className="w-full text-left text-sm text-foreground hover:text-primary rounded-sm py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                    >
                      {item.title}
                    </button>
                  ) : (
                    <p className="text-sm py-0.5">{item.title}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">✓ Нет элементов, требующих внимания</p>
          )}
        </section>
      </div>
    </div>
  );
}

function FunnelStep({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex-1 min-w-0 rounded-md bg-muted/60 px-1.5 py-1.5">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold tabular-nums leading-tight mt-0.5">{value}</p>
    </div>
  );
}

function FunnelRate({ value }: { value: string }) {
  return (
    <div className="flex flex-col items-center justify-center shrink-0 w-10 text-[10px] font-medium text-muted-foreground">
      <span aria-hidden>↓</span>
      <span>{value}</span>
    </div>
  );
}

export function OfferOverviewSkeleton() {
  return (
    <div className="grid gap-3">
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.95fr)_minmax(260px,1fr)]">
        <div className="ui-card p-4 h-[230px] animate-pulse bg-muted/60" />
        <div className="ui-card p-4 h-[230px] animate-pulse bg-muted/60" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="ui-card p-4 h-[180px] animate-pulse bg-muted/60" />
        <div className="ui-card p-4 h-[180px] animate-pulse bg-muted/60" />
        <div className="ui-card p-4 h-[180px] animate-pulse bg-muted/60" />
        <div className="ui-card p-4 h-[180px] animate-pulse bg-muted/60" />
      </div>
    </div>
  );
}
