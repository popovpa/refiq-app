import { lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import { StatCard, type StatTone } from '@/shared/components/StatCard';
import { Skeleton } from '@/shared/components/Skeleton';
import { cn } from '@/shared/utils/cn';
import { formatBucket, formatChange, formatMetric, formatPercent, qualityNote } from './format';
import { palette } from './charts/theme';
import type { Metric } from './types';

const ComboChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.ComboChart })));
const DonutChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.DonutChart })));
const HorizontalBarChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.HorizontalBarChart })));
const ColumnChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.ColumnChart })));
const LineChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.LineChart })));
const BubbleChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.BubbleChart })));
const FunnelChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.FunnelChart })));
const SankeyChartView = lazy(() => import('./charts/views').then((mod) => ({ default: mod.SankeyChart })));

function ChartFrame({ height, children }: { height: number; children: ReactNode }) {
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  if (!ready) return <div style={{ height }} />;
  return <Suspense fallback={<div style={{ height }} />}>{children}</Suspense>;
}

export { palette };

export function AnalyticsSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, index) => (
          <Skeleton key={index} className="h-[118px]" />
        ))}
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}

export function AnalyticsError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="ui-card flex flex-col items-center px-6 py-14 text-center">
      <p className="max-w-md text-sm text-foreground">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 h-9 rounded-md bg-primary px-4 text-[13px] font-semibold text-primary-foreground"
      >
        Повторить
      </button>
    </div>
  );
}

export function CoverageNote({ clickhouse, partial }: { clickhouse?: string; partial?: boolean }) {
  if (clickhouse !== 'unavailable' && !partial) return null;
  const text = clickhouse === 'unavailable'
    ? 'Поведенческие события сейчас недоступны. Клики, конверсии и комиссии показаны из учёта RefIQ.'
    : 'Часть показателей посчитана по неполной выборке измерений.';
  return <p className="text-xs text-muted-foreground">{text}</p>;
}

export function KpiGrid({
  items,
}: {
  items: Array<{ title: string; metric?: Metric | null; icon: LucideIcon; tone?: StatTone; hint?: string }>;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {items.map((item) => (
        <div key={item.title} title={item.hint} className="min-w-0">
          <StatCard
            compact
            title={item.title}
            icon={item.icon}
            tone={item.tone}
            value={formatMetric(item.metric)}
            trend={formatChange(item.metric?.change_pct)}
            trendLabel={qualityNote(item.metric)}
            className="h-full"
          />
        </div>
      ))}
    </div>
  );
}

export function Panel({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('ui-card min-w-0 p-4', className)}>
      <div className="mb-3 min-w-0">
        <h2 className="ui-section-title">{title}</h2>
        {subtitle ? <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function EmptyChart({ label = 'Нет данных за выбранный период' }: { label?: string }) {
  return <p className="py-12 text-center text-sm text-muted-foreground">{label}</p>;
}

export function TrendChart({
  rows,
}: {
  rows: Array<{ bucket: string; clicks: number; conversions: number; cr: string | null }>;
}) {
  const data = useMemo(() => rows.map((row) => ({
    label: formatBucket(row.bucket),
    clicks: row.clicks,
    conversions: row.conversions,
    cr: row.cr === null ? null : Number(row.cr),
  })), [rows]);
  if (!data.length) return <EmptyChart />;
  return (
    <ChartFrame height={288}>
      <ComboChartView rows={data} />
    </ChartFrame>
  );
}

export function Donut({
  rows,
  total,
  caption = 'кликов',
}: {
  rows: Array<{ label: string; clicks: number }>;
  total: number;
  caption?: string;
}) {
  const data = rows.filter((row) => row.clicks > 0);
  if (!data.length) return <EmptyChart />;
  return (
    <div className="grid min-w-0 items-center gap-3 sm:grid-cols-[minmax(0,1.2fr)_minmax(128px,0.8fr)]">
      <ChartFrame height={220}>
        <DonutChartView rows={data} total={total} caption={caption} />
      </ChartFrame>
      <ul className="space-y-1">
        {data.map((row, index) => (
          <li key={row.label} className="flex items-center justify-between gap-3 text-xs">
            <span className="flex min-w-0 items-center gap-2">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: palette[index % palette.length] }} />
              <span className="truncate">{row.label}</span>
            </span>
            <span className="text-muted-foreground">{total > 0 ? formatPercent((row.clicks / total) * 100) : '—'}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BubbleChart({
  rows,
}: {
  rows: Array<{ label: string; clicks: number; conversions: number; epc: string | null; cr: string | null; commission: string | null; currency?: string | null; kind?: string }>;
}) {
  const data = useMemo(
    () => rows.filter((row) => row.epc !== null && Number.isFinite(Number(row.epc))),
    [rows],
  );
  if (!data.length) return <EmptyChart label="Нет источников с рассчитанным EPC" />;
  return (
    <ChartFrame height={288}>
      <BubbleChartView rows={data} />
    </ChartFrame>
  );
}

export function MetricLines({
  rows,
  lines,
  unit = 'percent',
}: {
  rows: Array<Record<string, string | number | null>>;
  lines: Array<{ key: string; name: string; color: string }>;
  unit?: 'percent' | 'seconds';
}) {
  const hasValue = rows.some((row) => lines.some((line) => {
    const value = row[line.key];
    return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  }));
  if (!rows.length || !hasValue) return <EmptyChart />;
  return (
    <ChartFrame height={288}>
      <LineChartView rows={rows} lines={lines} unit={unit} />
    </ChartFrame>
  );
}

export function MilestoneBars({ rows }: { rows: Array<{ milestone: number; value: string | null }> }) {
  const data = rows.map((row) => ({ label: `${row.milestone}%`, value: row.value === null ? null : Number(row.value) }));
  if (data.every((row) => row.value === null)) return <EmptyChart label="Нет измерений прокрутки" />;
  return (
    <ChartFrame height={256}>
      <ColumnChartView rows={data} />
    </ChartFrame>
  );
}

export function EfficiencyList({
  rows,
  formula,
}: {
  rows: Array<{ label: string; value: string | null }>;
  formula: string;
}) {
  if (!rows.length) return <EmptyChart />;
  const chartRows = rows.map((row) => ({
    label: row.label,
    value: row.value === null || !Number.isFinite(Number(row.value)) ? null : Number(row.value),
  }));
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">{formula}</p>
      <ChartFrame height={Math.max(148, chartRows.length * 36)}>
        <HorizontalBarChartView rows={chartRows} />
      </ChartFrame>
    </div>
  );
}

export function FlowList({ rows }: { rows: Array<{ source: string; target: string; value: number }> }) {
  if (!rows.length) return <EmptyChart label="Недостаточно связанных просмотров для пути" />;
  const limited = rows.slice(0, 12);
  const nodes = new Set<string>();
  limited.forEach((row) => {
    nodes.add(row.source);
    nodes.add(row.target);
  });
  return (
    <ChartFrame height={Math.max(240, nodes.size * 36)}>
      <SankeyChartView rows={limited} />
    </ChartFrame>
  );
}

export function FunnelGraphic({
  steps,
}: {
  steps: Array<{ label: string; value: string | null; rate: string | null; available: boolean; definition: string }>;
}) {
  if (!steps.length) return <EmptyChart />;
  return (
    <ChartFrame height={380}>
      <FunnelChartView steps={steps} />
    </ChartFrame>
  );
}

export function LossList({
  rows,
}: {
  rows: Array<{ from: string; to: string; retained: string | null; lost: string | null; available: boolean }>;
}) {
  if (!rows.length) return <EmptyChart />;
  const chartRows = rows.map((row) => ({
    label: `${row.from} → ${row.to}`,
    value: row.available && row.lost !== null && Number.isFinite(Number(row.lost)) ? Number(row.lost) : null,
  }));
  return (
    <ChartFrame height={Math.max(148, chartRows.length * 36)}>
      <HorizontalBarChartView rows={chartRows} />
    </ChartFrame>
  );
}

export function DataTable<T extends object>({
  columns,
  rows,
}: {
  columns: Array<{ key: string; label: string; sort?: (row: T) => string | number | null; render: (row: T) => ReactNode }>;
  rows: T[];
}) {
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null);
  const ordered = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((item) => item.key === sort.key);
    if (!column?.sort) return rows;
    return [...rows].sort((left, right) => {
      const a = column.sort?.(left) ?? '';
      const b = column.sort?.(right) ?? '';
      const result = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b), 'ru');
      return sort.dir === 'asc' ? result : -result;
    });
  }, [columns, rows, sort]);
  if (!rows.length) return <EmptyChart />;
  return (
    <div className="overflow-x-auto">
      <table className="ui-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>
                {column.sort ? (
                  <button
                    type="button"
                    className="font-semibold uppercase"
                    onClick={() => setSort((current) => ({ key: column.key, dir: current?.key === column.key && current.dir === 'desc' ? 'asc' : 'desc' }))}
                  >
                    {column.label}
                  </button>
                ) : column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordered.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column.key}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OfferLink({ href, label }: { href?: string | null; label: string }) {
  if (!href) return <span>{label}</span>;
  return <Link to={href} className="font-medium text-brand hover:underline">{label}</Link>;
}
