import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { cn } from '@/shared/utils/cn';
import {
  formatPostbackDate,
  sdkSnippet,
  siteSdkLabel,
  siteStatusClass,
  siteStatusLabel,
  type BusinessSite,
} from './types';

export function SiteDrawer({
  siteId,
  onClose,
  onDisable,
  onDelete,
}: {
  siteId: number;
  onClose: () => void;
  onDisable: () => void;
  onDelete: (site: BusinessSite) => void;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<BusinessSite>({
    queryKey: ['business', 'sites', siteId],
    queryFn: () => api.get(`/business/sites/${siteId}`),
    refetchInterval: (query) => (query.state.data?.sdk_status === 'not_detected' ? 4000 : false),
  });

  const check = useMutation({
    mutationFn: () => api.post<BusinessSite>(`/business/sites/${siteId}/check`),
    onSuccess: (site) => {
      queryClient.setQueryData(['business', 'sites', siteId], site);
      queryClient.invalidateQueries({ queryKey: ['business', 'sites'] });
      queryClient.invalidateQueries({ queryKey: ['business', 'sdk', 'credential'] });
      addToast(
        site.sdk_status === 'connected' ? 'SDK подключен' : 'SDK ещё не обнаружен',
        site.sdk_status === 'connected' ? 'success' : 'error',
      );
    },
    onError: () => addToast('Не удалось проверить подключение', 'error'),
  });

  const enable = useMutation({
    mutationFn: () => api.post<BusinessSite>(`/business/sites/${siteId}/enable`),
    onSuccess: (site) => {
      queryClient.setQueryData(['business', 'sites', siteId], site);
      queryClient.invalidateQueries({ queryKey: ['business', 'sites'] });
      queryClient.invalidateQueries({ queryKey: ['business', 'sdk', 'credential'] });
      addToast('Сайт включён', 'success');
    },
    onError: () => addToast('Не удалось включить сайт', 'error'),
  });

  const rename = useMutation({
    mutationFn: (name: string) => api.patch<BusinessSite>(`/business/sites/${siteId}`, { name }),
    onSuccess: (site) => {
      queryClient.setQueryData(['business', 'sites', siteId], site);
      queryClient.invalidateQueries({ queryKey: ['business', 'sites'] });
      addToast('Название сохранено', 'success');
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      addToast(apiError?.error?.message || 'Не удалось сохранить название', 'error');
    },
  });

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const copy = async (value: string) => {
    await navigator.clipboard.writeText(value);
    addToast('Скопировано', 'success');
  };

  const snippet = data ? sdkSnippet(data.site_key) : '';

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <aside className="relative ui-card w-full max-w-lg h-full shadow-soft flex flex-col border-l" role="dialog" aria-modal="true">
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border/70">
          <div className="min-w-0">
            <h2 className="ui-section-title truncate">{data?.name || 'Сайт'}</h2>
            {data && <p className="text-sm text-muted-foreground truncate mt-1">{data.domain}</p>}
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-5">
          {isLoading || !data ? (
            <Skeleton className="h-64 rounded-xl" />
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn('ui-badge', siteStatusClass(data.display_status))}>
                  {siteStatusLabel(data.display_status)}
                </span>
                <span className="text-sm text-muted-foreground">{siteSdkLabel(data.sdk_status)}</span>
              </div>

              <label className="block">
                <span className="ui-label">Название</span>
                <input
                  className="ui-input"
                  defaultValue={data.name}
                  onBlur={(event) => {
                    const next = event.target.value.trim();
                    if (next && next !== data.name) rename.mutate(next);
                  }}
                />
              </label>

              <section>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <p className="text-xs font-medium text-muted-foreground">Код подключения</p>
                  <Button type="button" size="sm" variant="ghost" onClick={() => copy(snippet)}>
                    <Copy size={14} />
                    Скопировать код
                  </Button>
                </div>
                <pre className="text-xs bg-muted rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{snippet}</pre>
              </section>

              <div className="rounded-lg border border-border/70 bg-muted/30 p-3 space-y-1">
                <p className="text-sm font-medium">Состояние JS SDK</p>
                {data.last_success_at ? (
                  <p className="text-sm text-muted-foreground">
                    Последнее событие {formatPostbackDate(data.last_success_at, true)}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">SDK ещё не обнаружен</p>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="secondary" onClick={() => check.mutate()} disabled={check.isPending}>
                  {check.isPending ? 'Проверка...' : 'Проверить подключение'}
                </Button>
                {data.status === 'active' ? (
                  <Button type="button" variant="secondary" onClick={onDisable}>
                    Отключить
                  </Button>
                ) : (
                  <Button type="button" variant="secondary" onClick={() => enable.mutate()} disabled={enable.isPending}>
                    Включить
                  </Button>
                )}
                {data.can_delete && (
                  <Button type="button" variant="ghost" onClick={() => onDelete(data)}>
                    Удалить
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
