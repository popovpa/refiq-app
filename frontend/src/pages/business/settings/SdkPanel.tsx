import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { cn } from '@/shared/utils/cn';
import {
  formatPostbackDate,
  postbackStatusClass,
  sdkSnippet,
  sdkStatusLabel,
  type SdkCredentialCreated,
  type SdkCredentialStatus,
} from './types';

const QUERY_KEY = ['business', 'sdk', 'credential'] as const;

export function SdkPanel({ domain }: { domain: string }) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<SdkCredentialStatus>({
    queryKey: QUERY_KEY,
    queryFn: () => api.get('/business/sdk/credential'),
    refetchInterval: (query) =>
      query.state.data?.integration_status === 'awaiting_first_request' ? 4000 : false,
  });

  const createScript = useMutation({
    mutationFn: () => api.post<SdkCredentialCreated>('/business/sdk/credential'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ['business', 'dashboard'] });
    },
    onError: () => addToast('Не удалось создать SCRIPT_ID', 'error'),
  });

  const copy = async (value: string) => {
    await navigator.clipboard.writeText(value);
    addToast('Скопировано', 'success');
  };

  if (isLoading || !data) {
    return <Skeleton className="h-64 rounded-xl" />;
  }

  const configured = data.configured;
  const scriptId = data.script_id || '';
  const snippet = configured && scriptId ? sdkSnippet(scriptId) : '';
  const status = data.integration_status;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-muted-foreground">Установите RefIQ SDK на ваш сайт.</p>
        <span className={cn('ui-badge shrink-0', postbackStatusClass(status))}>{sdkStatusLabel(status)}</span>
      </div>

      {configured ? (
        <>
          <section className="space-y-3">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Идентификатор</h3>
            <div className="rounded-lg border border-border/70 p-3 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">SCRIPT_ID</p>
              <code className="text-sm break-all">{scriptId}</code>
              {data.created_at ? (
                <p className="text-sm text-muted-foreground">Создан {formatPostbackDate(data.created_at)}</p>
              ) : null}
            </div>
          </section>

          <section>
            <div className="flex items-center justify-between gap-2 mb-2">
              <p className="text-xs font-medium text-muted-foreground">Код подключения</p>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-label="Копировать код подключения"
                onClick={() => copy(snippet)}
              >
                <Copy size={14} />
                Скопировать
              </Button>
            </div>
            <pre className="text-xs bg-muted rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{snippet}</pre>
          </section>
        </>
      ) : (
        <section className="rounded-lg border border-border/70 p-3 space-y-3">
          <p className="text-sm">SCRIPT_ID ещё не создан.</p>
          <p className="text-sm text-muted-foreground">
            Создайте короткий идентификатор подключения. Он будет подставлен в код сниппета.
          </p>
          <Button type="button" size="sm" onClick={() => createScript.mutate()} disabled={createScript.isPending}>
            {createScript.isPending ? 'Создание...' : 'Создать SCRIPT_ID'}
          </Button>
        </section>
      )}

      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground">Домены</p>
        <div className="text-sm">{domain}</div>
      </div>

      <div className="rounded-lg border border-border/70 bg-muted/30 p-3 space-y-1">
        <p className="text-sm font-medium">Статус подключения</p>
        {data.last_success_at ? (
          <p className="text-sm text-muted-foreground">
            Последний успешный запрос {formatPostbackDate(data.last_success_at, true)}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">Последний запрос — не получен</p>
        )}
      </div>
    </div>
  );
}
