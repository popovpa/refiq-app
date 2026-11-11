import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { analyticsQuery, formatMetric } from './format';
import { refiqChartBaseOptions } from './charts/theme';
import { OverviewTab } from './tabs';
import { ANALYTICS_TABS, BUSINESS_FILTERS, PARTNER_FILTERS, type Metric, type OverviewData } from './types';

const metric = (value: string | null, unit = 'count'): Metric => ({
  value,
  change_pct: null,
  quality: value === null ? 'unavailable' : 'reliable',
  reason: value === null ? 'no_measurements' : null,
  unit,
  currency: unit === 'money' ? 'RUB' : null,
  samples: null,
  coverage: null,
});

describe('analytics section', () => {
  it('exposes six tabs and keeps partner filters inside the partner scope', () => {
    expect(ANALYTICS_TABS.map((item) => item.label)).toEqual([
      'Обзор',
      'Воронка',
      'Поведение',
      'Источники',
      'Качество трафика',
      'Производительность',
    ]);
    expect(PARTNER_FILTERS).not.toContain('partner');
    expect(PARTNER_FILTERS).not.toContain('site');
    const search = new URLSearchParams('period=30d&site=10&offer=4&device=mobile');
    const query = analyticsQuery({ from: '2026-10-01T00:00:00.000Z', to: '2026-10-20T00:00:00.000Z', timezone: 'UTC' }, search, PARTNER_FILTERS);
    expect(query).toContain('offer_id=4');
    expect(query).toContain('device=mobile');
    expect(query).not.toContain('site');
    expect(analyticsQuery({ from: 'a', to: 'b', timezone: 'UTC' }, search, BUSINESS_FILTERS)).toContain('site_id=10');
  });

  it('does not replace a missing metric with zero', () => {
    expect(formatMetric(metric(null, 'percent'))).toBe('—');
    expect(formatMetric(metric('10.00', 'money'))).toContain('10');
  });

  it('renders overview values from the API payload', () => {
    const data: OverviewData = {
      meta: {
        role: 'business',
        from: '2026-10-01T00:00:00Z',
        to: '2026-10-20T00:00:00Z',
        timezone: 'UTC',
        clickhouse: 'ok',
        definitions: { clicks: 'Клики трекера', conversions: '', cr: '', commission: '', epc: '', source: '', roi: 'Нет расходов' },
      },
      kpis: {
        clicks: metric('3'),
        conversions: metric('2'),
        cr: metric('66.67', 'percent'),
        commission: metric('10.00', 'money'),
        epc: metric(null, 'money'),
      },
      timeseries: [{ bucket: '2026-10-10', clicks: 3, conversions: 2, cr: '66.67' }],
      sources: [{ key: 'EMAIL', label: 'Email', kind: 'tracking_link', clicks: 3, conversions: 2, cr: '66.67', epc: null, commission: '10.00', currency: 'RUB', commission_reason: null, share: '100.00', roi: null, roi_reason: 'media_spend_not_collected' }],
      source_total: 3,
      source_quality: 'reliable',
      source_reason: null,
      offers: [],
      efficiency: { dimension: 'partners', metric: 'cr', formula: 'CR = конверсии / клики × 100', rows: [] },
    };
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <OverviewTab data={data} />
      </MemoryRouter>,
    );
    expect(html).toContain('Клики');
    expect(html).toContain('66,67%');
    expect(html).toContain('Email');
    expect(html).not.toContain('Яндекс');
    expect(html.toLowerCase()).not.toContain('highcharts.com');
    expect(refiqChartBaseOptions.credits?.enabled).toBe(false);
    expect(refiqChartBaseOptions.exporting?.chartOptions?.credits?.enabled).toBe(false);
  });
});
