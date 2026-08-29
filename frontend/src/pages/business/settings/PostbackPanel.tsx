import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { cn } from '@/shared/utils/cn';
import {
  POSTBACK_AUTH_EXAMPLE,
  POSTBACK_ENDPOINT,
  formatPostbackDate,
  maskPostbackToken,
  postbackCurlExample,
  postbackStatusClass,
  postbackStatusLabel,
  type PostbackCredentialStatus,
  type PostbackTokenCreated,
} from './types';

const QUERY_KEY = ['business', 'postback', 'credential'] as const;

export function PostbackPanel() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [confirmRotate, setConfirmRotate] = useState(false);

  const { data, isLoading } = useQuery<PostbackCredentialStatus>({
    queryKey: QUERY_KEY,
    queryFn: () => api.get('/business/postback/credential'),
  });

  const createToken = useMutation({
    mutationFn: () => api.post<PostbackTokenCreated>('/business/postback/credential'),
    onSuccess: (result) => {
      setPlaintext(result.token);
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: () => addToast('Не удалось создать Bearer Token', 'error'),
  });

  const rotateToken = useMutation({
    mutationFn: () => api.post<PostbackTokenCreated>('/business/postback/credential/rotate'),
    onSuccess: (result) => {
      setConfirmRotate(false);
      setPlaintext(result.token);
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
    onError: () => addToast('Не удалось перевыпустить Bearer Token', 'error'),
  });

  const copy = async (value: string, message = 'Скопировано') => {
    await navigator.clipboard.writeText(value);
    addToast(message, 'success');
  };

  if (isLoading || !data) {
    return <Skeleton className="h-64 rounded-xl" />;
  }

  const curl = postbackCurlExample();
  const status = data.integration_status;
  const configured = data.configured;

  return (
    <>
      <div className="space-y-5">
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Передавайте подтверждённые конверсии с backend вашей системы в RefIQ.
          </p>
          <span className={cn('ui-badge shrink-0', postbackStatusClass(status))}>{postbackStatusLabel(status)}</span>
        </div>

        <section className="space-y-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Авторизация</h3>
          {configured ? (
            <div className="rounded-lg border border-border/70 p-3 space-y-3">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Bearer Token</p>
                <code className="text-sm break-all">{maskPostbackToken(data.token_suffix)}</code>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm text-muted-foreground">
                  <p>
                    Статус: <span className="text-foreground">Активен</span>
                  </p>
                  {data.created_at ? <p>Создан {formatPostbackDate(data.created_at)}</p> : null}
                </div>
                <Button type="button" size="sm" variant="secondary" onClick={() => setConfirmRotate(true)}>
                  Перевыпустить Token
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-border/70 p-3 space-y-3">
              <p className="text-sm">Bearer Token ещё не создан.</p>
              <p className="text-sm text-muted-foreground">
                Создайте секретный токен для авторизации server-to-server запросов. Используйте его только на backend
                вашей системы.
              </p>
              <Button
                type="button"
                size="sm"
                onClick={() => createToken.mutate()}
                disabled={createToken.isPending}
              >
                {createToken.isPending ? 'Создание...' : 'Создать Bearer Token'}
              </Button>
            </div>
          )}
        </section>

        <section className="space-y-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Endpoint</h3>
          <Detail label="Метод">POST</Detail>
          <Detail label="Endpoint">
            <CopyRow value={POSTBACK_ENDPOINT} onCopy={() => copy(POSTBACK_ENDPOINT)} />
          </Detail>
          {configured ? (
            <Detail label="Authorization">
              <CopyRow value={POSTBACK_AUTH_EXAMPLE} onCopy={() => copy(POSTBACK_AUTH_EXAMPLE)} />
            </Detail>
          ) : null}
          <Detail label="Content-Type">application/json</Detail>
        </section>

        <section className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Как подключить</h3>
          <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
            <li>Сохраните rqcid после партнёрского перехода.</li>
            <li>При конверсии отправьте POST на Endpoint.</li>
            <li>Передайте Bearer Token в Authorization header.</li>
          </ol>
        </section>

        {configured ? (
          <section className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Пример запроса</h3>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-label="Копировать пример cURL"
                onClick={() => copy(curl)}
              >
                <Copy size={14} />
                cURL
              </Button>
            </div>
            <pre className="text-xs bg-muted rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{curl}</pre>
          </section>
        ) : null}

        <section className="rounded-lg border border-border/70 bg-muted/30 p-3 space-y-1">
          <p className="text-sm font-medium">Статус подключения</p>
          {data.last_success_at ? (
            <p className="text-sm text-muted-foreground">
              Последний успешный запрос {formatPostbackDate(data.last_success_at, true)}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">Последний запрос — не получен</p>
          )}
        </section>
      </div>

      {plaintext && (
        <TokenReveal
          token={plaintext}
          onCopy={() => copy(plaintext, 'Bearer Token скопирован')}
          onAck={() => setPlaintext(null)}
        />
      )}

      {confirmRotate && (
        <ConfirmDialog
          title="Перевыпустить Bearer Token?"
          confirmLabel="Перевыпустить"
          pending={rotateToken.isPending}
          onClose={() => setConfirmRotate(false)}
          onConfirm={() => rotateToken.mutate()}
        >
          <p>Текущая интеграция использует существующий Token.</p>
          <p>
            После активации нового токена старый перестанет работать. Не забудьте обновить секрет в backend вашей
            системы.
          </p>
        </ConfirmDialog>
      )}
    </>
  );
}

function TokenReveal({
  token,
  onCopy,
  onAck,
}: {
  token: string;
  onCopy: () => void;
  onAck: () => void;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.stopImmediatePropagation();
      onAck();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onAck]);
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/40" />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <h2 className="ui-section-title">Bearer Token создан</h2>
        <p className="text-sm text-muted-foreground">
          Скопируйте токен сейчас. После закрытия этого окна полностью посмотреть его снова будет нельзя.
        </p>
        <code className="block text-sm bg-muted rounded-lg p-3 break-all">{token}</code>
        <Button type="button" onClick={onCopy}>
          <Copy size={14} />
          Скопировать
        </Button>
        <p className="text-sm text-muted-foreground">
          Используйте: <code className="text-foreground">Authorization: Bearer {token}</code>
        </p>
        <p className="text-xs text-muted-foreground">
          Не используйте Bearer Token во frontend-коде. Храните его только в backend-конфигурации или secret storage
          вашей инфраструктуры.
        </p>
        <div className="flex justify-end">
          <Button type="button" variant="secondary" onClick={onAck}>
            Я сохранил токен
          </Button>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function CopyRow({ value, onCopy }: { value: string; onCopy: () => void }) {
  return (
    <div className="flex items-center gap-2 min-w-0">
      <code className="text-sm bg-muted px-2 py-1 rounded-md truncate">{value}</code>
      <Button type="button" size="sm" variant="ghost" aria-label={`Копировать ${value}`} onClick={onCopy}>
        <Copy size={14} />
        Копировать
      </Button>
    </div>
  );
}
