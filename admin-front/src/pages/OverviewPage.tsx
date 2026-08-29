import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import { PageTitle, StatusBadge, formatNumber } from '@/components/ui';
import { QueryState } from '@/components/Table';

interface Overview {
  counts: Record<string, number>;
  activity_24h: Record<string, number>;
  health: Record<string, { status: string; label: string; last_at?: string | null }>;
}

export function OverviewPage() {
  const query = useQuery({ queryKey: ['overview'], queryFn: () => api.get<Overview>('/overview') });
  const data = query.data;
  return (
    <div>
      <PageTitle title="Обзор" />
      <QueryState loading={query.isLoading} error={query.error}>
        {data && (
          <div className="space-y-4">
            <section className="grid grid-cols-5 gap-3">
              {([
                ['Бизнесы', data.counts.businesses, '/businesses'],
                ['Подключённые сайты', data.counts.connected_sites, '/sites'],
                ['Партнёры', data.counts.partners, '/partners'],
                ['Активные офферы', data.counts.active_offers, '/offers?status=active'],
                ['Активные ссылки', data.counts.active_tracking_links, '/tracking-links?status=ACTIVE'],
              ] as const).map(([label, value, href]) => (
                <Link key={label} to={href} className="ui-card p-3 hover:bg-muted/40">
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="text-xl font-semibold tabular-nums mt-1">{formatNumber(value)}</div>
                </Link>
              ))}
            </section>
            <section>
              <h2 className="ui-section-title mb-2">Активность · последние 24 часа</h2>
              <div className="grid grid-cols-4 gap-3">
                {[
                  ['Клики', data.activity_24h.clicks],
                  ['Конверсии', data.activity_24h.conversions],
                  ['Принятые Postback', data.activity_24h.accepted_postbacks],
                  ['Отклонённые Postback', data.activity_24h.rejected_postbacks],
                ].map(([label, value]) => (
                  <div key={label} className="ui-card p-3">
                    <div className="text-xs text-muted-foreground">{label}</div>
                    <div className="text-xl font-semibold tabular-nums mt-1">{formatNumber(value as number)}</div>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h2 className="ui-section-title mb-2">Состояние сервисов</h2>
              <div className="grid grid-cols-4 gap-3">
                {Object.entries({
                  'Редиректы трекинга': data.health.tracking_redirects,
                  'Приём clickstream': data.health.clickstream_receiving,
                  'Приём Postback': data.health.postback_receiving,
                  'Отправка email': data.health.email_sending,
                }).map(([label, item]) => (
                  <div key={label} className="ui-card p-3">
                    <div className="text-xs text-muted-foreground mb-2">{label}</div>
                    <StatusBadge status={item.status} />
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </QueryState>
    </div>
  );
}
