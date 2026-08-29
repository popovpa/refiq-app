import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { entityHref } from '@/lib/navigation';
import { PageTitle, StatusBadge, formatDateTime } from '@/components/ui';
import { QueryState } from '@/components/Table';
import { EntityLink } from '@/components/EntityLink';
import { RqcidLink } from '@/components/RqcidLink';

interface TraceStep {
  key: string;
  label: string;
  status: string;
  at?: string | null;
  reason_code?: string | null;
  entity?: { type: string; id: string | number } | null;
}

const MARK: Record<string, string> = {
  ok: '✓',
  error: '✕',
  pending: '○',
  missing: '○',
  unavailable: '○',
};

const GROUP_LABELS: Record<string, string> = {
  tracking: 'Трекинг',
  behavior: 'Поведение',
  conversion: 'Конверсия',
  finance: 'Финансы',
};

const SUMMARY_VALUE: Record<string, string> = {
  OK: 'OK',
  Failed: 'Ошибка',
  Unavailable: 'Недоступно',
  'Not received': 'Не получен',
  Created: 'Создана',
  'Not Created': 'Не создана',
};

export function TracePage() {
  const { rqcid } = useParams();
  const query = useQuery({
    queryKey: ['trace', rqcid],
    queryFn: () => api.get<any>(`/trace/${rqcid}`),
    enabled: Boolean(rqcid),
  });
  const data = query.data;
  return (
    <QueryState loading={query.isLoading} error={query.error}>
      {data && (
        <div className="space-y-4">
          <PageTitle title={`Трассировка ${data.rqcid}`} />
          <div className="ui-card p-4 grid grid-cols-3 gap-3 text-sm">
            <div>rqcid: <RqcidLink rqcid={data.rqcid} /></div>
            <div>
              Бизнес:{' '}
              <EntityLink type="business" id={data.context.business?.id}>{data.context.business?.name}</EntityLink>
            </div>
            <div>
              Оффер: <EntityLink type="offer" id={data.context.offer?.id}>{data.context.offer?.name}</EntityLink>
            </div>
            <div>
              Партнёр:{' '}
              <EntityLink type="partner" id={data.context.partner?.id}>{data.context.partner?.name}</EntityLink>
            </div>
            <div>
              Ссылка:{' '}
              <EntityLink type="tracking_link" id={data.context.tracking_link?.id}>
                {data.context.tracking_link?.short_code}
              </EntityLink>
            </div>
            <div>Кампания: {data.context.campaign?.name || '—'}</div>
            <div>Создан: {formatDateTime(data.context.created_at)}</div>
            <div>
              Статус: <StatusBadge status={data.context.status} />
            </div>
          </div>
          <div className="ui-card p-4">
            <h2 className="ui-section-title mb-3">Диагностическая сводка</h2>
            <div className="grid grid-cols-5 gap-3 text-sm mb-3">
              {[
                ['Трафик', data.summary.traffic],
                ['SDK-трекинг', data.summary.sdk_tracking],
                ['Postback', data.summary.postback],
                ['Конверсия', data.summary.conversion],
                ['Комиссия', data.summary.commission],
              ].map(([label, value]) => (
                <div key={label}>
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="font-medium">{SUMMARY_VALUE[String(value)] || value}</div>
                </div>
              ))}
            </div>
            {data.summary.problem && (
              <div className="text-sm">
                <span className="text-muted-foreground">Проблема: </span>
                {data.summary.problem_code && <code className="mr-2 text-xs">{data.summary.problem_code}</code>}
                {data.summary.problem}
              </div>
            )}
          </div>
          {(['tracking', 'behavior', 'conversion', 'finance'] as const).map((group) => (
            <section key={group} className="ui-card p-4">
              <h2 className="ui-section-title mb-3 text-xs tracking-wider">{GROUP_LABELS[group]}</h2>
              <ol className="space-y-2">
                {(data.timeline[group] as TraceStep[]).map((step) => {
                  const href = step.entity ? entityHref(step.entity.type, step.entity.id) : null;
                  return (
                    <li key={`${group}-${step.key}-${step.at}`} className="flex items-start gap-3 text-sm">
                      <span className="w-5 text-center font-medium">{MARK[step.status] || '·'}</span>
                      <div className="min-w-0">
                        <div>
                          {href ? (
                            <Link to={href} className="text-primary hover:underline">
                              {step.label}
                            </Link>
                          ) : (
                            step.label
                          )}
                          {step.at && <span className="ml-2 text-xs text-muted-foreground">{formatDateTime(step.at)}</span>}
                        </div>
                        {step.reason_code && (
                          <div className="text-xs text-muted-foreground">
                            Причина: <code>{step.reason_code}</code>
                          </div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
          {!data.clickstream_available && (
            <p className="text-xs text-muted-foreground">
              Поведенческие события недоступны, пока не подключён ClickHouse.
            </p>
          )}
        </div>
      )}
    </QueryState>
  );
}
