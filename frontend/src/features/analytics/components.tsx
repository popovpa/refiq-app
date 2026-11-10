import { useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import type { LucideIcon } from 'lucide-react';
import { StatCard, type StatTone } from '@/shared/components/StatCard';
import { Skeleton } from '@/shared/components/Skeleton';
import { chartTheme } from '@/shared/charts/theme';
import { cn } from '@/shared/utils/cn';
import { formatBucket, formatChange, formatMetric, qualityNote } from './format';
import { formatNumber as formatCount } from '@/shared/utils/format';
import type { Metric } from './types';

export const palette = ['#4E70BE', '#586AD9', '#287F61', '#6E62A8', '#1F6A6A', '#99661E', '#B6C9DE'];

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
  const [visible, setVisible] = useState({ clicks: true, conversions: true, cr: true });
  const data = rows.map((row) => ({
    label: formatBucket(row.bucket),
    clicks: row.clicks,
    conversions: row.conversions,
    cr: row.cr === null ? null : Number(row.cr),
  }));
  if (!data.length) return <EmptyChart />;
  return (
    <div className="min-w-0">
      <div className="mb-2 flex flex-wrap gap-2">
        {([
          ['clicks', 'Клики', chartTheme.series],
          ['conversions', 'Конверсии', chartTheme.success],
          ['cr', 'CR', chartTheme.primary],
        ] as const).map(([key, label, color]) => (
          <button
            key={key}
            type="button"
            onClick={() => setVisible((current) => ({ ...current, [key]: !current[key] }))}
            className={cn('rounded-md px-2 py-1 text-xs font-semibold', visible[key] ? 'bg-muted text-foreground' : 'text-muted-foreground')}
          >
            <span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: color }} />
            {label}
          </button>
        ))}
      </div>
      <div className="h-72 w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={chartTheme.grid} vertical={false} />
            <XAxis dataKey="label" tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis yAxisId="left" tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
            <YAxis yAxisId="right" orientation="right" tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={36} unit="%" />
            <Tooltip />
            <Line yAxisId="left" type="monotone" dataKey="clicks" name="Клики" stroke={chartTheme.series} strokeWidth={2} dot={false} hide={!visible.clicks} />
            <Line yAxisId="left" type="monotone" dataKey="conversions" name="Конверсии" stroke={chartTheme.success} strokeWidth={2} dot={false} hide={!visible.conversions} />
            <Line yAxisId="right" type="monotone" dataKey="cr" name="CR, %" stroke={chartTheme.primary} strokeWidth={2} dot={false} hide={!visible.cr} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function Donut({
  rows,
  total,
}: {
  rows: Array<{ label: string; clicks: number }>;
  total: number;
}) {
  const data = rows.filter((row) => row.clicks > 0);
  if (!data.length) return <EmptyChart />;
  return (
    <div className="min-w-0">
      <div className="relative h-52">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="clicks" nameKey="label" innerRadius={58} outerRadius={82} paddingAngle={2} stroke="none">
              {data.map((row, index) => (
                <Cell key={row.label} fill={palette[index % palette.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="text-lg font-semibold text-foreground">{formatCount(total)}</div>
            <div className="text-[11px] text-muted-foreground">кликов</div>
          </div>
        </div>
      </div>
      <ul className="mt-2 space-y-1">
        {data.map((row, index) => (
          <li key={row.label} className="flex items-center justify-between gap-3 text-xs">
            <span className="flex min-w-0 items-center gap-2">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: palette[index % palette.length] }} />
              <span className="truncate">{row.label}</span>
            </span>
            <span className="text-muted-foreground">{formatCount(row.clicks)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function BubbleChart({
  rows,
}: {
  rows: Array<{ label: string; clicks: number; conversions: number; epc: string | null; cr: string | null; commission: string | null; kind: string }>;
}) {
  const data = rows
    .filter((row) => row.epc !== null)
    .map((row, index) => ({
      ...row,
      x: row.clicks,
      y: Number(row.epc),
      z: Math.max(row.conversions, 1),
      fill: palette[index % palette.length],
    }));
  if (!data.length) return <EmptyChart label="Нет источников с рассчитанным EPC" />;
  return (
    <div className="h-72 min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={chartTheme.grid} />
          <XAxis dataKey="x" name="Клики" tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis dataKey="y" name="EPC" tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
          <ZAxis dataKey="z" range={[80, 360]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
          <Scatter data={data} name="Источник">
            {data.map((row) => (
              <Cell key={row.label} fill={row.fill} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MetricLines({
  rows,
  lines,
}: {
  rows: Array<Record<string, string | number | null>>;
  lines: Array<{ key: string; name: string; color: string }>;
}) {
  if (!rows.length) return <EmptyChart />;
  return (
    <div className="h-72 min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={chartTheme.grid} vertical={false} />
          <XAxis dataKey="label" tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {lines.map((line) => (
            <Line key={line.key} type="monotone" dataKey={line.key} name={line.name} stroke={line.color} strokeWidth={2} dot={false} connectNulls={false} />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MilestoneBars({ rows }: { rows: Array<{ milestone: number; value: string | null }> }) {
  const data = rows.map((row) => ({ label: `${row.milestone}%`, value: row.value === null ? null : Number(row.value) }));
  if (data.every((row) => row.value === null)) return <EmptyChart label="Нет измерений прокрутки" />;
  return (
    <div className="h-64 min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke={chartTheme.grid} vertical={false} />
          <XAxis dataKey="label" tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: chartTheme.tick, fontSize: 11 }} axisLine={false} tickLine={false} width={36} unit="%" />
          <Tooltip />
          <Bar dataKey="value" name="Доля, %" fill={chartTheme.series} radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function EfficiencyList({
  rows,
  valueKey,
  formula,
}: {
  rows: Array<{ label: string; value: string | null }>;
  valueKey?: string;
  formula: string;
}) {
  const numbers = rows.map((row) => Number(row.value)).filter((value) => Number.isFinite(value));
  const max = Math.max(...numbers, 0);
  if (!rows.length) return <EmptyChart />;
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">{formula}</p>
      {rows.map((row) => {
        const numeric = Number(row.value);
        const width = Number.isFinite(numeric) && max > 0 ? Math.max(4, (numeric / max) * 100) : 0;
        return (
          <div key={row.label}>
            <div className="mb-1 flex items-center justify-between gap-3 text-xs">
              <span className="truncate font-medium text-foreground">{row.label}</span>
              <span className="shrink-0 text-muted-foreground">{valueKey === 'count' ? formatCount(row.value) : row.value === null ? '—' : `${formatCount(row.value)}%`}</span>
            </div>
            <div className="h-2 rounded-full bg-muted">
              <div className="h-2 rounded-full bg-brand" style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function FlowList({ rows }: { rows: Array<{ source: string; target: string; value: number }> }) {
  const max = Math.max(...rows.map((row) => row.value), 0);
  if (!rows.length) return <EmptyChart label="Недостаточно связанных просмотров для пути" />;
  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <div key={`${row.source}-${row.target}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-xs">
          <div className="min-w-0">
            <p className="truncate text-foreground">{row.source} → {row.target}</p>
            <div className="mt-1 h-1.5 rounded-full bg-muted">
              <div className="h-1.5 rounded-full bg-[#6E62A8]" style={{ width: `${max ? (row.value / max) * 100 : 0}%` }} />
            </div>
          </div>
          <span className="text-muted-foreground">{formatCount(row.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function FunnelGraphic({
  steps,
}: {
  steps: Array<{ label: string; value: string | null; rate: string | null; available: boolean; definition: string }>;
}) {
  const colors = ['#4E70BE', '#586AD9', '#6E62A8', '#287F61', '#1F6A6A'];
  return (
    <div className="space-y-2">
      {steps.map((step, index) => (
        <div key={step.label} title={step.definition} className="mx-auto" style={{ width: `${100 - index * 12}%` }}>
          <div
            className={cn('flex h-14 items-center justify-between gap-3 px-4', step.available ? 'text-white' : 'text-foreground')}
            style={{
              background: step.available ? colors[index] : '#E6EDF5',
              clipPath: 'polygon(3% 0, 97% 0, 100% 100%, 0 100%)',
            }}
          >
            <span className="truncate text-sm font-semibold">{step.label}</span>
            <span className="shrink-0 text-right text-xs">
              <span className="block text-sm font-semibold">{step.available ? formatCount(step.value) : '—'}</span>
              <span>{step.available && step.rate ? `${formatCount(step.rate)}%` : step.available ? '' : 'недоступно'}</span>
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

export function LossList({
  rows,
}: {
  rows: Array<{ from: string; to: string; retained: string | null; lost: string | null; available: boolean }>;
}) {
  if (!rows.length) return <EmptyChart />;
  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <div key={`${row.from}-${row.to}`}>
          <div className="mb-1 flex justify-between gap-2 text-xs">
            <span className="text-foreground">{row.from} → {row.to}</span>
            <span className="text-muted-foreground">{row.available && row.lost !== null ? `потери ${formatCount(row.lost)}%` : '—'}</span>
          </div>
          <div className="h-2 rounded-full bg-muted">
            <div
              className="h-2 rounded-full bg-brand"
              style={{ width: row.available && row.retained !== null ? `${Math.min(100, Number(row.retained))}%` : '0%' }}
            />
          </div>
        </div>
      ))}
    </div>
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
