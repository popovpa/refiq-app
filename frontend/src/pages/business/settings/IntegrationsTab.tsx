import { useQuery } from '@tanstack/react-query';
import { Button } from '@/shared/components/Button';
import { api } from '@/shared/api/client';
import { cn } from '@/shared/utils/cn';
import type { IntegrationKind, PostbackCredentialStatus, SdkCredentialStatus } from './types';
import { postbackStatusClass, postbackStatusLabel, sdkStatusLabel } from './types';

export function IntegrationsTab({
  onOpen,
  onManageSites,
}: {
  onOpen: (kind: IntegrationKind) => void;
  onManageSites: () => void;
}) {
  const { data: postback } = useQuery<PostbackCredentialStatus>({
    queryKey: ['business', 'postback', 'credential'],
    queryFn: () => api.get('/business/postback/credential'),
  });
  const { data: sdk } = useQuery<SdkCredentialStatus>({
    queryKey: ['business', 'sdk', 'credential'],
    queryFn: () => api.get('/business/sdk/credential'),
    refetchInterval: (query) =>
      query.state.data?.integration_status === 'awaiting_first_request' ? 4000 : false,
  });

  const postbackStatus = postback?.integration_status || 'not_configured';
  const sdkStatus = sdk?.integration_status || 'not_configured';

  return (
    <div className="space-y-4">
      <div>
        <h2 className="ui-section-title">Интеграции</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Подключите сайт и backend вашей компании к RefIQ.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <article className="ui-card p-5 flex flex-col gap-3 min-w-0">
          <div>
            <h3 className="text-sm font-semibold">Postback / S2S</h3>
            <p className="text-xs text-muted-foreground mt-0.5">Backend → RefIQ</p>
          </div>
          <p className="text-sm text-muted-foreground">Передача подтверждённых конверсий с backend.</p>
          <span className={cn('ui-badge w-fit', postbackStatusClass(postbackStatus))}>
            {postbackStatusLabel(postbackStatus)}
          </span>
          <div className="pt-1 mt-auto">
            <Button type="button" variant="secondary" size="sm" onClick={() => onOpen('postback')}>
              Настроить
            </Button>
          </div>
        </article>

        <article className="ui-card p-5 flex flex-col gap-3 min-w-0">
          <div>
            <h3 className="text-sm font-semibold">Web Tracking</h3>
            <p className="text-xs text-muted-foreground mt-0.5">JS SDK → сайты бизнеса</p>
          </div>
          <p className="text-sm text-muted-foreground">
            {sdk?.sites_count
              ? `${sdk.sites_count} ${siteWord(sdk.sites_count)}, ${sdk.connected_sites || 0} подключены`
              : 'Добавьте сайт, чтобы подключить web tracking и начать получать события.'}
          </p>
          <span className={cn('ui-badge w-fit', postbackStatusClass(sdkStatus))}>{sdkStatusLabel(sdkStatus)}</span>
          <div className="pt-1 mt-auto">
            <Button type="button" variant="secondary" size="sm" onClick={onManageSites}>
              Управление сайтами
            </Button>
          </div>
        </article>
      </div>
    </div>
  );
}

function siteWord(count: number) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return 'сайт';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'сайта';
  return 'сайтов';
}
