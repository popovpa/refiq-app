import { ArrowLeftRight, Banknote, Clock3, Gauge, MousePointerClick, Percent, Timer, Users, Wallet, Activity } from 'lucide-react';
import { chartTheme } from '@/shared/charts/theme';
import {
  BubbleChart,
  CoverageNote,
  DataTable,
  Donut,
  EfficiencyList,
  FlowList,
  FunnelGraphic,
  KpiGrid,
  LossList,
  MetricLines,
  MilestoneBars,
  OfferLink,
  Panel,
  TrendChart,
} from './components';
import { formatBucket, formatPercent, moneyText } from './format';
import type { BehaviorData, FunnelData, OverviewData, PerformanceData, QualityData, SourcesData } from './types';

export function OverviewTab({ data }: { data: OverviewData }) {
  return (
    <div className="space-y-4">
      <CoverageNote clickhouse={data.meta.clickhouse} partial={data.source_quality === 'partial'} />
      <KpiGrid
        items={[
          { title: 'Клики', metric: data.kpis.clicks, icon: MousePointerClick, tone: 'blue', hint: data.meta.definitions.clicks },
          { title: 'Конверсии', metric: data.kpis.conversions, icon: ArrowLeftRight, tone: 'green', hint: data.meta.definitions.conversions },
          { title: 'CR', metric: data.kpis.cr, icon: Percent, tone: 'purple', hint: data.meta.definitions.cr },
          { title: 'Комиссия', metric: data.kpis.commission, icon: Wallet, tone: 'teal', hint: data.meta.definitions.commission },
          { title: 'EPC', metric: data.kpis.epc, icon: Banknote, tone: 'pink', hint: data.meta.definitions.epc },
        ]}
      />
      <div className="grid gap-4 xl:grid-cols-3">
        <Panel title="Динамика кликов и конверсий" className="xl:col-span-2">
          <TrendChart rows={data.timeseries} />
        </Panel>
        <Panel title="Источники трафика" subtitle={data.meta.definitions.source}>
          <Donut rows={data.sources.map((row) => ({ label: row.label, clicks: row.clicks }))} total={data.source_total} />
        </Panel>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Топ офферов">
          <DataTable
            columns={[
              { key: 'label', label: 'Оффер', render: (row) => <OfferLink href={String(row.href || '')} label={String(row.label)} /> },
              { key: 'clicks', label: 'Клики', sort: (row) => Number(row.clicks), render: (row) => String(row.clicks) },
              { key: 'conversions', label: 'Конверсии', sort: (row) => Number(row.conversions), render: (row) => String(row.conversions) },
              { key: 'cr', label: 'CR', sort: (row) => Number(row.cr), render: (row) => formatPercent(row.cr as string | null) },
              { key: 'commission', label: 'Комиссия', sort: (row) => Number(row.commission), render: (row) => moneyText(row.commission as string | null, row.currency as string | null) },
            ]}
            rows={data.offers}
          />
        </Panel>
        <Panel title={data.efficiency.dimension === 'partners' ? 'Эффективность партнёров' : 'Эффективность ссылок'}>
          <EfficiencyList
            formula={data.efficiency.formula}
            rows={data.efficiency.rows.map((row) => ({ label: row.label, value: row.cr }))}
          />
        </Panel>
      </div>
    </div>
  );
}

export function FunnelTab({ data }: { data: FunnelData }) {
  return (
    <div className="space-y-4">
      <CoverageNote clickhouse={data.meta.clickhouse} />
      <div className="grid gap-4 xl:grid-cols-5">
        <Panel title="Воронка" className="xl:col-span-3">
          <FunnelGraphic steps={data.steps} />
        </Panel>
        <div className="space-y-4 xl:col-span-2">
          <Panel title="Потери на этапах">
            <LossList rows={data.losses} />
          </Panel>
          <Panel title="Конверсии по статусам">
            <Donut
              rows={data.statuses.map((item) => ({ label: item.label, clicks: item.count }))}
              total={data.statuses.reduce((sum, item) => sum + item.count, 0)}
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}

export function BehaviorTab({ data }: { data: BehaviorData }) {
  const partial = Object.values(data.kpis).some((metric) => metric.quality === 'partial');
  return (
    <div className="space-y-4">
      <CoverageNote clickhouse={data.meta.clickhouse} partial={partial} />
      <KpiGrid
        items={[
          { title: 'Сессии', metric: data.kpis.sessions, icon: Users, tone: 'blue', hint: data.meta.definitions.pages_per_session },
          { title: 'Вовлечённость', metric: data.kpis.engagement, icon: Activity, tone: 'purple', hint: data.meta.definitions.engagement },
          { title: 'Среднее время', metric: data.kpis.duration, icon: Clock3, tone: 'teal', hint: data.meta.definitions.duration },
          { title: 'Глубина просмотра', metric: data.kpis.depth, icon: Timer, tone: 'green', hint: data.meta.definitions.scroll },
          { title: 'Отказы', metric: data.kpis.bounce, icon: Percent, tone: 'pink', hint: data.meta.definitions.bounce },
        ]}
      />
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Глубина прокрутки" subtitle={data.meta.definitions.scroll}>
          <MilestoneBars rows={data.scroll} />
        </Panel>
        <Panel title="Пути пользователей" subtitle="Только соседние просмотры внутри одной сессии">
          <FlowList rows={data.paths} />
        </Panel>
      </div>
      <Panel title="Популярные страницы">
        <DataTable
          columns={[
            { key: 'page', label: 'Страница', render: (row) => <span className="break-all">{String(row.page)}</span> },
            { key: 'views', label: 'Просмотры', sort: (row) => Number(row.views), render: (row) => String(row.views) },
            { key: 'engagement', label: 'Вовлечённость', sort: (row) => Number(row.engagement), render: (row) => formatPercent(row.engagement as string | null) },
          ]}
          rows={data.pages}
        />
      </Panel>
    </div>
  );
}

export function SourcesTab({ data }: { data: SourcesData }) {
  return (
    <div className="space-y-4">
      <CoverageNote partial={data.source_quality === 'partial'} />
      <div className="grid gap-4 xl:grid-cols-5">
        <Panel title="Эффективность источников" subtitle="Ось X — клики, ось Y — EPC, размер — конверсии" className="xl:col-span-3">
          <BubbleChart rows={data.points} />
        </Panel>
        <Panel title="Распределение трафика" className="xl:col-span-2">
          <Donut rows={data.distribution.map((row) => ({ label: row.label, clicks: row.clicks }))} total={data.distribution.reduce((sum, row) => sum + row.clicks, 0)} />
        </Panel>
      </div>
      <Panel title="Источники" subtitle={data.meta.definitions.source}>
        <DataTable
          columns={[
            { key: 'label', label: 'Источник', render: (row) => <span>{String(row.label)} <span className="text-muted-foreground">({String(row.kind)})</span></span> },
            { key: 'clicks', label: 'Клики', sort: (row) => Number(row.clicks), render: (row) => String(row.clicks) },
            { key: 'conversions', label: 'Конверсии', sort: (row) => Number(row.conversions), render: (row) => String(row.conversions) },
            { key: 'cr', label: 'CR', sort: (row) => Number(row.cr), render: (row) => formatPercent(row.cr as string | null) },
            { key: 'epc', label: 'EPC', sort: (row) => Number(row.epc), render: (row) => moneyText(row.epc as string | null, row.currency as string | null) },
            { key: 'commission', label: 'Комиссия', sort: (row) => Number(row.commission), render: (row) => moneyText(row.commission as string | null, row.currency as string | null) },
            { key: 'roi', label: 'ROI', render: () => <span title={data.meta.definitions.roi}>—</span> },
          ]}
          rows={data.rows}
        />
      </Panel>
    </div>
  );
}

export function QualityTab({ data }: { data: QualityData }) {
  const partial = Object.values(data.kpis).some((metric) => metric.quality === 'partial');
  return (
    <div className="space-y-4">
      <CoverageNote clickhouse={data.meta.clickhouse} partial={partial} />
      <KpiGrid
        items={[
          { title: 'Достигли сайта', metric: data.kpis.reached, icon: MousePointerClick, tone: 'blue', hint: data.meta.definitions.reached },
          { title: 'Вовлечённость', metric: data.kpis.engagement, icon: Activity, tone: 'purple', hint: data.meta.definitions.engagement },
          { title: 'Bounce Rate', metric: data.kpis.bounce, icon: Percent, tone: 'pink', hint: data.meta.definitions.bounce },
          { title: 'Среднее время', metric: data.kpis.duration, icon: Clock3, tone: 'teal', hint: data.meta.definitions.duration },
          { title: 'Страниц за сессию', metric: data.kpis.pages_per_session, icon: Users, tone: 'green', hint: data.meta.definitions.pages_per_session },
        ]}
      />
      <div className="grid gap-4 xl:grid-cols-5">
        <Panel title="Качество по дням" className="xl:col-span-3">
          <MetricLines
            rows={data.series.map((row) => ({
              label: formatBucket(row.bucket),
              reached: row.reached_rate === null || row.reached_rate === undefined ? null : Number(row.reached_rate),
              engagement: row.engagement === null || row.engagement === undefined ? null : Number(row.engagement),
            }))}
            lines={[
              { key: 'reached', name: 'Дошли до сайта, %', color: chartTheme.series },
              { key: 'engagement', name: 'Вовлечённость, %', color: chartTheme.success },
            ]}
          />
        </Panel>
        <Panel
          title={data.dimension === 'partners' ? 'Качество по партнёрам' : 'Качество по ссылкам'}
          subtitle="Доля кликов, для которых есть page_view"
          className="xl:col-span-2"
        >
          <EfficiencyList
            formula="Показатель = достигшие сайта / клики. Пропущенные события SDK не считаются отказом."
            rows={data.comparison.map((row) => ({ label: row.label, value: row.reached_rate }))}
          />
        </Panel>
      </div>
    </div>
  );
}

export function PerformanceTab({ data }: { data: PerformanceData }) {
  const partial = Object.values(data.kpis).some((metric) => metric.quality === 'partial');
  return (
    <div className="space-y-4">
      <CoverageNote clickhouse={data.meta.clickhouse} partial={partial} />
      <KpiGrid
        items={[
          { title: 'LCP (P75)', metric: data.kpis.lcp, icon: Gauge, tone: 'blue', hint: data.meta.definitions.lcp },
          { title: 'INP (P75)', metric: data.kpis.inp, icon: Timer, tone: 'purple', hint: data.meta.definitions.inp },
          { title: 'CLS (P75)', metric: data.kpis.cls, icon: Activity, tone: 'green', hint: data.meta.definitions.cls },
          { title: 'Вес страницы', metric: data.kpis.weight, icon: Wallet, tone: 'teal', hint: data.meta.definitions.weight },
          { title: 'Ошибки загрузки', metric: data.kpis.load_errors, icon: Percent, tone: 'pink', hint: data.meta.definitions.load_errors },
        ]}
      />
      <div className="grid gap-4 xl:grid-cols-5">
        <Panel title="Скорость загрузки" subtitle="P75 LCP по исходным измерениям, отдельно для mobile и desktop" className="xl:col-span-3">
          <MetricLines
            rows={data.series.map((row) => ({
              label: formatBucket(row.bucket),
              mobile: row.mobile === null || row.mobile === undefined ? null : Number(row.mobile),
              desktop: row.desktop === null || row.desktop === undefined ? null : Number(row.desktop),
            }))}
            lines={[
              { key: 'mobile', name: 'Mobile', color: chartTheme.series },
              { key: 'desktop', name: 'Desktop', color: chartTheme.success },
            ]}
          />
        </Panel>
        <Panel title="Самые медленные страницы" className="xl:col-span-2">
          <DataTable
            columns={[
              { key: 'page', label: 'Страница', render: (row) => <span className="break-all">{String(row.page)}</span> },
              { key: 'lcp', label: 'LCP', sort: (row) => Number(row.lcp), render: (row) => (row.lcp ? `${row.lcp} мс` : '—') },
              { key: 'weight', label: 'Вес', render: (row) => (row.weight ? `${row.weight} Б` : '—') },
            ]}
            rows={data.pages}
          />
        </Panel>
      </div>
    </div>
  );
}
