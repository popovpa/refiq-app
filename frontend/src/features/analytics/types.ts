export type Quality = 'reliable' | 'partial' | 'unavailable';

export interface Metric {
  value: string | null;
  change_pct: string | null;
  quality: Quality;
  reason: string | null;
  unit: string | null;
  currency: string | null;
  samples: number | null;
  coverage: string | null;
}

export interface AnalyticsMeta {
  role: 'business' | 'partner';
  from: string;
  to: string;
  timezone: string;
  clickhouse: string;
  definitions: Record<string, string>;
}

export interface SeriesPoint {
  bucket: string;
  clicks: number;
  conversions: number;
  cr: string | null;
  reached?: number | null;
  reached_rate?: string | null;
  engagement?: string | null;
  mobile?: string | null;
  desktop?: string | null;
}

export interface SourceRow {
  key: string;
  label: string;
  kind: string;
  clicks: number;
  conversions: number;
  cr: string | null;
  epc: string | null;
  commission: string | null;
  currency: string | null;
  commission_reason: string | null;
  share: string | null;
  roi: string | null;
  roi_reason: string | null;
}

export interface EntityRow {
  id: string | null;
  label: string;
  href: string | null;
  clicks: number;
  conversions: number;
  cr: string | null;
  commission: string | null;
  currency: string | null;
  epc: string | null;
  ownership: string | null;
  commission_reason: string | null;
  reached_rate: string | null;
  engagement: string | null;
  bounce: string | null;
  quality: Quality;
}

export interface OverviewData {
  meta: AnalyticsMeta;
  kpis: Record<string, Metric>;
  timeseries: SeriesPoint[];
  sources: SourceRow[];
  source_total: number;
  source_quality: Quality;
  source_reason: string | null;
  offers: EntityRow[];
  efficiency: {
    dimension: 'partners' | 'links';
    metric: string;
    formula: string;
    rows: EntityRow[];
  };
}

export interface FunnelStep {
  key: string;
  label: string;
  value: string | null;
  rate: string | null;
  available: boolean;
  quality: Quality;
  reason: string | null;
  definition: string;
}

export interface FunnelData {
  meta: AnalyticsMeta;
  steps: FunnelStep[];
  losses: Array<{ from: string; to: string; retained: string | null; lost: string | null; available: boolean }>;
  statuses: Array<{ key: string; label: string; count: number }>;
}

export interface BehaviorData {
  meta: AnalyticsMeta;
  kpis: Record<string, Metric>;
  scroll: Array<{ milestone: number; value: string | null; quality: Quality; reason: string | null }>;
  paths: Array<{ source: string; target: string; value: number }>;
  pages: Array<{ page: string; views: number; engagement: string | null; quality: Quality }>;
}

export interface SourcesData {
  meta: AnalyticsMeta;
  points: SourceRow[];
  distribution: SourceRow[];
  rows: SourceRow[];
  source_quality: Quality;
  source_reason: string | null;
}

export interface QualityData {
  meta: AnalyticsMeta;
  kpis: Record<string, Metric>;
  series: SeriesPoint[];
  comparison: EntityRow[];
  dimension: 'partners' | 'links';
}

export interface PerformanceData {
  meta: AnalyticsMeta;
  kpis: Record<string, Metric>;
  series: SeriesPoint[];
  pages: Array<{ page: string; lcp: string | null; weight: string | null; samples: number; quality: Quality }>;
}

export interface FilterOption {
  id: number;
  name: string;
}

export interface AnalyticsFiltersData {
  role: 'business' | 'partner';
  offers: FilterOption[];
  campaigns: FilterOption[];
  links: FilterOption[];
  partners: FilterOption[];
  sites: FilterOption[];
  traffic_sources: Array<{ code: string; label: string }>;
  devices: string[];
}

export const ANALYTICS_TABS = [
  { id: 'overview', path: '', label: 'Обзор' },
  { id: 'funnel', path: 'funnel', label: 'Воронка' },
  { id: 'behavior', path: 'behavior', label: 'Поведение' },
  { id: 'sources', path: 'sources', label: 'Источники' },
  { id: 'quality', path: 'quality', label: 'Качество трафика' },
  { id: 'performance', path: 'performance', label: 'Производительность' },
] as const;

export type AnalyticsTab = (typeof ANALYTICS_TABS)[number]['id'];

export const BUSINESS_FILTERS = ['offer', 'partner', 'campaign', 'site', 'source', 'device', 'landing'] as const;
export const PARTNER_FILTERS = ['offer', 'campaign', 'link', 'utm_source', 'utm_campaign', 'device', 'landing'] as const;
