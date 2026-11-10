import { useEffect } from 'react';
import { NavLink, Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { PageHeading } from '@/shared/dateRange/PageHeading';
import { useDateRange } from '@/shared/dateRange/useDateRange';
import { useAuth } from '@/shared/hooks/useAuth';
import { cn } from '@/shared/utils/cn';
import { AnalyticsError, AnalyticsSkeleton } from './components';
import { analyticsQuery } from './format';
import { BehaviorTab, FunnelTab, OverviewTab, PerformanceTab, QualityTab, SourcesTab } from './tabs';
import {
  ANALYTICS_TABS,
  BUSINESS_FILTERS,
  PARTNER_FILTERS,
  type AnalyticsFiltersData,
  type AnalyticsTab,
  type BehaviorData,
  type FunnelData,
  type OverviewData,
  type PerformanceData,
  type QualityData,
  type SourcesData,
} from './types';

function errorText(error: unknown): string {
  const message = (error as { error?: { message?: string } } | null)?.error?.message;
  return message || 'Не удалось загрузить аналитику';
}

export function AnalyticsPage() {
  const { session } = useAuth();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const range = useDateRange('30d');
  const queryClient = useQueryClient();
  const role = session?.active_role === 'partner' ? 'partner' : 'business';
  const base = `/${role}/analytics`;
  const businessId = session?.active_business_id ?? null;
  const filterKeys = role === 'partner' ? PARTNER_FILTERS : BUSINESS_FILTERS;
  const query = analyticsQuery(range.apiParams, searchParams, filterKeys);
  const suffix = location.pathname.startsWith(base) ? location.pathname.slice(base.length).replace(/^\//, '') : null;
  const tab = ANALYTICS_TABS.find((item) => item.path === suffix)?.id;

  useEffect(() => {
    queryClient.removeQueries({
      predicate: (item) => item.queryKey[0] === 'analytics' && item.queryKey[2] !== role,
    });
  }, [businessId, queryClient, role]);

  const filters = useQuery({
    queryKey: ['analytics-filters', role, businessId],
    queryFn: ({ signal }) => api.get<AnalyticsFiltersData>('/analytics/filters', { signal }),
    enabled: suffix !== null,
  });
  const report = useQuery({
    queryKey: ['analytics', tab, role, businessId, query],
    queryFn: ({ signal }) => api.get<OverviewData | FunnelData | BehaviorData | SourcesData | QualityData | PerformanceData>(
      `/analytics/${tab}?${query}`,
      { signal },
    ),
    enabled: Boolean(tab) && suffix !== null,
  });

  if (!location.pathname.startsWith(base)) {
    return <Navigate to={{ pathname: base, search: location.search }} replace />;
  }
  if (!tab) {
    return <Navigate to={{ pathname: base, search: location.search }} replace />;
  }

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  return (
    <div className="space-y-4">
      <PageHeading title="Аналитика" dateRangeFilter="header" defaultPreset="30d" />
      <div className="flex items-center gap-3">
        <nav className="flex min-w-0 flex-1 gap-1 overflow-x-auto" aria-label="Разделы аналитики">
          {ANALYTICS_TABS.map((item) => (
            <NavLink
              key={item.id}
              end={item.path === ''}
              to={{ pathname: item.path ? `${base}/${item.path}` : base, search: location.search }}
              className={({ isActive }) => cn(
                'rounded-lg px-3 py-1.5 text-[13px] font-semibold whitespace-nowrap',
                isActive ? 'bg-brand-soft text-brand' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <FilterBar
        role={role}
        options={filters.data}
        searchParams={searchParams}
        onChange={setFilter}
      />
      {report.isError ? (
        <AnalyticsError message={errorText(report.error)} onRetry={() => report.refetch()} />
      ) : report.isPending || !report.data ? (
        <AnalyticsSkeleton />
      ) : (
        <TabView tab={tab} data={report.data} />
      )}
    </div>
  );
}

function TabView({
  tab,
  data,
}: {
  tab: AnalyticsTab;
  data: OverviewData | FunnelData | BehaviorData | SourcesData | QualityData | PerformanceData;
}) {
  if (tab === 'overview') return <OverviewTab data={data as OverviewData} />;
  if (tab === 'funnel') return <FunnelTab data={data as FunnelData} />;
  if (tab === 'behavior') return <BehaviorTab data={data as BehaviorData} />;
  if (tab === 'sources') return <SourcesTab data={data as SourcesData} />;
  if (tab === 'quality') return <QualityTab data={data as QualityData} />;
  return <PerformanceTab data={data as PerformanceData} />;
}

function FilterBar({
  role,
  options,
  searchParams,
  onChange,
}: {
  role: 'business' | 'partner';
  options?: AnalyticsFiltersData;
  searchParams: URLSearchParams;
  onChange: (key: string, value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <SelectFilter label="Оффер" value={searchParams.get('offer') || ''} onChange={(value) => onChange('offer', value)} options={(options?.offers || []).map((item) => ({ value: String(item.id), label: item.name }))} />
      <SelectFilter label="Кампания" value={searchParams.get('campaign') || ''} onChange={(value) => onChange('campaign', value)} options={(options?.campaigns || []).map((item) => ({ value: String(item.id), label: item.name }))} />
      {role === 'partner' ? (
        <SelectFilter label="Ссылка" value={searchParams.get('link') || ''} onChange={(value) => onChange('link', value)} options={(options?.links || []).map((item) => ({ value: String(item.id), label: item.name }))} />
      ) : (
        <SelectFilter label="Партнёр" value={searchParams.get('partner') || ''} onChange={(value) => onChange('partner', value)} options={(options?.partners || []).map((item) => ({ value: String(item.id), label: item.name }))} />
      )}
      {role === 'business' ? (
        <SelectFilter label="Сайт" value={searchParams.get('site') || ''} onChange={(value) => onChange('site', value)} options={(options?.sites || []).map((item) => ({ value: String(item.id), label: item.name }))} />
      ) : null}
      <SelectFilter label="Источник" value={searchParams.get('source') || ''} onChange={(value) => onChange('source', value)} options={(options?.traffic_sources || []).map((item) => ({ value: item.code, label: item.label }))} />
      {role === 'partner' ? (
        <>
          <TextFilter label="UTM source" value={searchParams.get('utm_source') || ''} onChange={(value) => onChange('utm_source', value)} />
          <TextFilter label="UTM campaign" value={searchParams.get('utm_campaign') || ''} onChange={(value) => onChange('utm_campaign', value)} />
        </>
      ) : null}
      <SelectFilter
        label="Устройство"
        value={searchParams.get('device') || ''}
        onChange={(value) => onChange('device', value)}
        options={(options?.devices || ['mobile', 'desktop', 'tablet']).map((item) => ({ value: item, label: item }))}
      />
      <TextFilter label="Страница" value={searchParams.get('landing') || ''} onChange={(value) => onChange('landing', value)} />
    </div>
  );
}

function SelectFilter({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex min-w-[140px] flex-col gap-1 text-[11px] font-medium text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-md border border-border bg-card px-2 text-[13px] text-foreground"
      >
        <option value="">Все</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

function TextFilter({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex min-w-[140px] flex-col gap-1 text-[11px] font-medium text-muted-foreground">
      {label}
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-md border border-border bg-card px-2 text-[13px] text-foreground"
      />
    </label>
  );
}
