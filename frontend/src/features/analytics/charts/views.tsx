import type Highcharts from 'highcharts';
import { formatPercent, moneyText } from '../format';
import { formatNumber } from '@/shared/utils/format';
import { RefiqChart } from './RefiqChart';
import { chartColors, funnelColor, palette } from './theme';

const axisLabel = { style: { color: chartColors.tick, fontSize: '11px' } };

function axisBase(): Highcharts.XAxisOptions {
  return {
    lineWidth: 0,
    tickLength: 0,
    labels: axisLabel,
  };
}

function valueAxis(extra?: Highcharts.YAxisOptions): Highcharts.YAxisOptions {
  return {
    title: { text: undefined },
    gridLineColor: chartColors.grid,
    lineWidth: 0,
    tickLength: 0,
    labels: axisLabel,
    ...extra,
  };
}

function placeDonutCenter(chart: Highcharts.Chart, text: string) {
  const series = chart.series[0] as Highcharts.Series & { center?: number[] };
  const center = series?.center;
  if (!center) return;
  const x = chart.plotLeft + center[0];
  const y = chart.plotTop + center[1];
  const host = chart as Highcharts.Chart & { __centerLabel?: Highcharts.SVGElement };
  const label = host.__centerLabel ?? chart.renderer.label('', 0, 0, undefined, undefined, undefined, true).add();
  host.__centerLabel = label;
  label.attr({ text, x, y: y - 18, align: 'center' });
}

export type ComboRow = { label: string; clicks: number; conversions: number; cr: number | null };

export function ComboChart({ rows }: { rows: ComboRow[] }) {
  const options: Highcharts.Options = {
    chart: { spacingTop: 28 },
    xAxis: { ...axisBase(), categories: rows.map((row) => row.label) },
    yAxis: [
      valueAxis(),
      valueAxis({
        opposite: true,
        gridLineWidth: 0,
        labels: { ...axisLabel, format: '{value}%' },
      }),
    ],
    legend: { align: 'left', verticalAlign: 'top', floating: true, y: -8 },
    tooltip: { shared: true, valueDecimals: 2 },
    plotOptions: {
      spline: { lineWidth: 2.5, marker: { radius: 3, symbol: 'circle' } },
      column: { borderWidth: 0, borderRadius: 4, pointPadding: 0.15, groupPadding: 0.12 },
    },
    series: [
      {
        type: 'spline',
        name: 'Клики',
        color: chartColors.series,
        yAxis: 0,
        data: rows.map((row) => row.clicks),
      },
      {
        type: 'column',
        name: 'Конверсии',
        color: chartColors.success,
        yAxis: 0,
        data: rows.map((row) => row.conversions),
      },
      {
        type: 'spline',
        name: 'CR',
        color: chartColors.primary,
        yAxis: 1,
        connectNulls: false,
        tooltip: { valueSuffix: '%' },
        data: rows.map((row) => row.cr),
      },
    ],
  };
  return <RefiqChart options={options} height={288} />;
}

export function DonutChart({
  rows,
  total,
  caption,
}: {
  rows: Array<{ label: string; clicks: number }>;
  total: number;
  caption: string;
}) {
  const text = `<div style="text-align:center;line-height:1.15"><span style="font-size:18px;font-weight:650;color:${chartColors.ink}">${formatNumber(total)}</span><br/><span style="font-size:11px;color:${chartColors.tick}">${caption}</span></div>`;
  const options: Highcharts.Options = {
    chart: {
      type: 'pie',
      events: {
        render() {
          placeDonutCenter(this, text);
        },
      },
    },
    legend: { enabled: false },
    tooltip: {
      pointFormatter() {
        const share = total > 0 ? (this.y ?? 0) / total * 100 : 0;
        return `<span style="color:${this.color}">●</span> ${this.name}: <b>${formatNumber(this.y)}</b> (${formatPercent(share)})`;
      },
    },
    plotOptions: {
      pie: {
        innerSize: '68%',
        borderWidth: 2,
        borderColor: '#FFFFFF',
        dataLabels: { enabled: false },
        states: { hover: { halo: { size: 6 } } },
      },
    },
    series: [{
      type: 'pie',
      name: caption,
      data: rows.map((row, index) => ({
        name: row.label,
        y: row.clicks,
        color: palette[index % palette.length],
      })),
    }],
  };
  return <RefiqChart options={options} height={220} />;
}

export function HorizontalBarChart({
  rows,
}: {
  rows: Array<{ label: string; value: number | null }>;
}) {
  const finite = rows.map((row) => row.value).filter((value): value is number => value !== null && Number.isFinite(value));
  const max = Math.max(...finite, 0);
  const options: Highcharts.Options = {
    chart: { type: 'bar', spacingRight: 48 },
    xAxis: {
      ...axisBase(),
      categories: rows.map((row) => row.label),
      reversed: true,
    },
    yAxis: valueAxis({
      visible: false,
      min: 0,
      max: max <= 100 ? 100 : undefined,
      endOnTick: false,
    }),
    legend: { enabled: false },
    tooltip: {
      pointFormatter() {
        return this.y === null || this.y === undefined ? '—' : `<b>${formatPercent(this.y)}</b>`;
      },
    },
    plotOptions: {
      bar: {
        borderWidth: 0,
        borderRadius: 4,
        pointWidth: 10,
        color: chartColors.series,
        dataLabels: {
          enabled: true,
          crop: false,
          overflow: 'allow',
          style: { color: chartColors.tick, fontSize: '11px', fontWeight: '600', textOutline: 'none' },
          formatter() {
            return this.y === null || this.y === undefined ? '—' : formatPercent(this.y);
          },
        },
      },
    },
    series: [{
      type: 'bar',
      data: rows.map((row) => (row.value === null ? null : row.value)),
    }],
  };
  return <RefiqChart options={options} height={Math.max(148, rows.length * 36)} />;
}

export function ColumnChart({ rows }: { rows: Array<{ label: string; value: number | null }> }) {
  const options: Highcharts.Options = {
    chart: { type: 'column' },
    xAxis: { ...axisBase(), categories: rows.map((row) => row.label) },
    yAxis: valueAxis({ labels: { ...axisLabel, format: '{value}%' }, min: 0 }),
    legend: { enabled: false },
    tooltip: {
      pointFormatter() {
        return this.y === null || this.y === undefined ? 'Нет измерения' : `<b>${formatPercent(this.y)}</b> просмотров с прокруткой`;
      },
    },
    plotOptions: {
      column: {
        borderWidth: 0,
        borderRadius: 6,
        color: chartColors.series,
        dataLabels: {
          enabled: true,
          style: { color: chartColors.ink, fontSize: '11px', fontWeight: '600', textOutline: 'none' },
          formatter() {
            return this.y === null || this.y === undefined ? '' : formatPercent(this.y, 0);
          },
        },
      },
    },
    series: [{
      type: 'column',
      name: 'Глубина',
      data: rows.map((row) => row.value),
    }],
  };
  return <RefiqChart options={options} height={256} />;
}

export type LineSeries = { key: string; name: string; color: string };

export function LineChart({
  rows,
  lines,
  unit,
}: {
  rows: Array<Record<string, string | number | null>>;
  lines: LineSeries[];
  unit: 'percent' | 'seconds';
}) {
  const options: Highcharts.Options = {
    chart: { type: 'spline', spacingTop: 28 },
    xAxis: { ...axisBase(), categories: rows.map((row) => String(row.label ?? '')) },
    yAxis: valueAxis(unit === 'percent'
      ? { labels: { ...axisLabel, format: '{value}%' }, min: 0 }
      : { labels: { ...axisLabel, format: '{value} с' }, min: 0 }),
    legend: { align: 'left', verticalAlign: 'top', floating: true, y: -8 },
    tooltip: {
      shared: true,
      pointFormatter() {
        if (this.y === null || this.y === undefined) return '';
        const text = unit === 'percent' ? formatPercent(this.y) : `${formatPercent(this.y, 2).replace('%', '')} с`;
        return `<span style="color:${this.color}">●</span> ${this.series.name}: <b>${text}</b><br/>`;
      },
    },
    plotOptions: {
      spline: { lineWidth: 2.5, marker: { radius: 3, symbol: 'circle' }, connectNulls: false },
    },
    series: lines.map((line) => ({
      type: 'spline' as const,
      name: line.name,
      color: line.color,
      data: rows.map((row) => {
        const value = row[line.key];
        if (value === null || value === undefined || value === '') return null;
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return null;
        return unit === 'seconds' ? numeric / 1000 : numeric;
      }),
    })),
  };
  return <RefiqChart options={options} height={288} />;
}

export type BubbleRow = {
  label: string;
  clicks: number;
  conversions: number;
  epc: string | null;
  cr: string | null;
  commission: string | null;
  currency?: string | null;
};

export function BubbleChart({ rows }: { rows: BubbleRow[] }) {
  const options: Highcharts.Options = {
    chart: { type: 'bubble' },
    xAxis: { ...axisBase(), title: { text: 'Клики', style: axisLabel.style }, gridLineColor: chartColors.grid },
    yAxis: valueAxis({ title: { text: 'EPC', style: axisLabel.style } }),
    legend: { enabled: false },
    tooltip: {
      useHTML: true,
      headerFormat: '',
      pointFormatter() {
        const point = this.options as Highcharts.PointOptionsObject & {
          custom?: { conversions: number; cr: string | null; commission: string | null; currency: string | null };
        };
        const custom = point.custom;
        return [
          `<b>${this.name}</b>`,
          `Клики: ${formatNumber(this.x)}`,
          `Конверсии: ${formatNumber(custom?.conversions)}`,
          `CR: ${formatPercent(custom?.cr)}`,
          `EPC: ${moneyText(String(this.y ?? ''), custom?.currency)}`,
          `Комиссия: ${moneyText(custom?.commission, custom?.currency)}`,
        ].join('<br/>');
      },
    },
    plotOptions: {
      bubble: {
        minSize: 14,
        maxSize: 46,
        opacity: 0.78,
        marker: { fillOpacity: 0.78, lineWidth: 0 },
      },
    },
    series: [{
      type: 'bubble',
      data: rows.map((row, index) => ({
        x: row.clicks,
        y: Number(row.epc),
        z: Math.max(row.conversions, 0),
        name: row.label,
        color: palette[index % palette.length],
        custom: {
          conversions: row.conversions,
          cr: row.cr,
          commission: row.commission,
          currency: row.currency ?? null,
        },
      })),
    }],
  };
  return <RefiqChart options={options} height={288} />;
}

export type FunnelStep = {
  label: string;
  value: string | null;
  rate: string | null;
  available: boolean;
  definition: string;
};

export function FunnelChart({ steps }: { steps: FunnelStep[] }) {
  const options: Highcharts.Options = {
    chart: { type: 'funnel' },
    legend: { enabled: false },
    tooltip: {
      pointFormatter() {
        const custom = (this.options as Highcharts.PointOptionsObject & { custom?: { definition: string; available: boolean; rate: string | null } }).custom;
        if (!custom?.available) return `${this.name}<br/>Недоступно<br/>${custom?.definition ?? ''}`;
        return `${this.name}<br/><b>${formatNumber(this.y)}</b><br/>${formatPercent(custom?.rate)} от первого этапа<br/>${custom?.definition ?? ''}`;
      },
    },
    plotOptions: {
      funnel: {
        neckWidth: '30%',
        neckHeight: '0%',
        width: '74%',
        borderWidth: 4,
        borderColor: '#FFFFFF',
        minPointLength: 36,
        dataLabels: {
          enabled: true,
          inside: true,
          softConnector: false,
          connectorWidth: 0,
          useHTML: true,
          style: { textOutline: 'none', fontWeight: '600', fontSize: '12px' },
        },
      } as Highcharts.PlotFunnelOptions,
    },
    series: [{
      type: 'funnel',
      data: steps.map((step, index) => {
        const available = step.available && step.value !== null;
        return {
          name: step.label,
          y: available ? Number(step.value) : 0,
          color: funnelColor(index, available),
          custom: { definition: step.definition, available, rate: step.rate },
          dataLabels: {
            color: available ? '#FFFFFF' : chartColors.ink,
            formatter() {
              const point = this as unknown as Highcharts.Point & { custom?: { available: boolean; rate: string | null } };
              if (!point.custom?.available) return `${point.name}<br/>—<br/>недоступно`;
              return `${point.name}<br/>${formatNumber(point.y)}<br/>${formatPercent(point.custom.rate)}`;
            },
          },
        };
      }),
    }],
  };
  return <RefiqChart options={options} height={380} />;
}

export function SankeyChart({ rows }: { rows: Array<{ source: string; target: string; value: number }> }) {
  const names: string[] = [];
  rows.forEach((row) => {
    if (!names.includes(row.source)) names.push(row.source);
    if (!names.includes(row.target)) names.push(row.target);
  });
  const options: Highcharts.Options = {
    chart: { type: 'sankey' },
    tooltip: {
      headerFormat: '',
      pointFormatter() {
        const point = this as Highcharts.Point & { fromNode?: { name: string }; toNode?: { name: string }; weight?: number };
        if (point.fromNode && point.toNode) {
          return `${point.fromNode.name} → ${point.toNode.name}<br/><b>${formatNumber(point.weight)}</b> переходов`;
        }
        return `<b>${point.name}</b>`;
      },
    },
    plotOptions: {
      sankey: {
        nodeWidth: 14,
        nodePadding: 18,
        curveFactor: 0.45,
        linkOpacity: 0.35,
        minLinkWidth: 1,
        dataLabels: {
          style: { color: chartColors.ink, textOutline: 'none', fontSize: '11px', fontWeight: '500' },
          nodeFormatter() {
            const name = String((this as Highcharts.Point).name ?? '');
            return name.length > 28 ? `${name.slice(0, 26)}…` : name;
          },
        },
        states: { hover: { linkOpacity: 0.72 } },
      },
    },
    series: [{
      type: 'sankey',
      nodes: names.map((id, index) => ({ id, color: palette[index % palette.length] })),
      data: rows.map((row) => ({ from: row.source, to: row.target, weight: row.value })),
      colorByPoint: false,
    }],
  };
  return <RefiqChart options={options} height={Math.max(240, names.length * 36)} />;
}
