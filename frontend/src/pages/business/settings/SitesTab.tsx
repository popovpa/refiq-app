import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MoreHorizontal } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { EmptyState } from '@/shared/components/EmptyState';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { cn } from '@/shared/utils/cn';
import { AddSiteModal } from './AddSiteModal';
import { SiteDrawer } from './SiteDrawer';
import {
  sdkSnippet,
  siteSdkLabel,
  siteStatusClass,
  siteStatusLabel,
  type BusinessSite,
} from './types';

const QUERY_KEY = ['business', 'sites'] as const;

export function SitesTab() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [menu, setMenu] = useState<{ site: BusinessSite; rect: DOMRect } | null>(null);
  const [confirm, setConfirm] = useState<{ site: BusinessSite; type: 'disable' | 'delete' } | null>(null);

  const { data, isLoading } = useQuery<BusinessSite[]>({
    queryKey: QUERY_KEY,
    queryFn: () => api.get('/business/sites'),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: ['business', 'sdk', 'credential'] });
    queryClient.invalidateQueries({ queryKey: ['business', 'dashboard'] });
  };

  const createSite = useMutation({
    mutationFn: (payload: { url: string; name?: string }) => api.post<BusinessSite>('/business/sites', payload),
    onSuccess: (site) => {
      invalidate();
      setAddOpen(false);
      setAddError(null);
      setOpenId(site.id);
      addToast('Сайт добавлен', 'success');
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      setAddError(apiError?.error?.message || 'Не удалось добавить сайт');
    },
  });

  const disableSite = useMutation({
    mutationFn: (siteId: number) => api.post<BusinessSite>(`/business/sites/${siteId}/disable`),
    onSuccess: () => {
      invalidate();
      setConfirm(null);
      addToast('Сайт отключён', 'success');
    },
    onError: () => addToast('Не удалось отключить сайт', 'error'),
  });

  const enableSite = useMutation({
    mutationFn: (siteId: number) => api.post<BusinessSite>(`/business/sites/${siteId}/enable`),
    onSuccess: () => {
      invalidate();
      addToast('Сайт включён', 'success');
    },
    onError: () => addToast('Не удалось включить сайт', 'error'),
  });

  const deleteSite = useMutation({
    mutationFn: (siteId: number) => api.delete(`/business/sites/${siteId}`),
    onSuccess: () => {
      invalidate();
      setConfirm(null);
      setOpenId(null);
      addToast('Сайт удалён', 'success');
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      addToast(apiError?.error?.message || 'Не удалось удалить сайт', 'error');
    },
  });

  const copySdk = async (site: BusinessSite) => {
    await navigator.clipboard.writeText(sdkSnippet(site.site_key));
    addToast('Код SDK скопирован', 'success');
  };

  const checkSite = useMutation({
    mutationFn: (siteId: number) => api.post<BusinessSite>(`/business/sites/${siteId}/check`),
    onSuccess: (site) => {
      invalidate();
      addToast(
        site.sdk_status === 'connected' ? 'SDK подключен' : 'SDK ещё не обнаружен',
        site.sdk_status === 'connected' ? 'success' : 'error',
      );
    },
    onError: () => addToast('Не удалось проверить подключение', 'error'),
  });

  const sites = data || [];

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="ui-section-title">Сайты</h2>
          <p className="text-sm text-muted-foreground mt-1">Управляйте web tracking для каждого сайта бизнеса.</p>
        </div>
        <Button type="button" size="sm" onClick={() => { setAddError(null); setAddOpen(true); }}>
          + Добавить сайт
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, index) => (
            <Skeleton key={index} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : !sites.length ? (
        <EmptyState
          title="Сайтов пока нет"
          description="Добавьте сайт, чтобы подключить web tracking и начать получать события."
          action={{ label: 'Добавить сайт', onClick: () => { setAddError(null); setAddOpen(true); } }}
        />
      ) : (
        <div className="space-y-3">
          {sites.map((site) => (
            <article
              key={site.id}
              className="ui-card p-4 flex items-start justify-between gap-3 cursor-pointer"
              onClick={() => setOpenId(site.id)}
            >
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-semibold truncate">{site.domain}</p>
                <p className="text-sm text-muted-foreground truncate">{site.name}</p>
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className={cn('ui-badge', siteStatusClass(site.display_status))}>
                    {siteStatusLabel(site.display_status)}
                  </span>
                  <span className="text-xs text-muted-foreground">{siteSdkLabel(site.sdk_status)}</span>
                </div>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                data-site-menu-trigger={site.id}
                onClick={(event) => {
                  event.stopPropagation();
                  const rect = event.currentTarget.getBoundingClientRect();
                  setMenu((current) => (current?.site.id === site.id ? null : { site, rect }));
                }}
              >
                <MoreHorizontal size={16} />
              </Button>
            </article>
          ))}
        </div>
      )}

      {menu && (
        <SiteRowMenu
          site={menu.site}
          rect={menu.rect}
          onClose={() => setMenu(null)}
          onOpen={() => {
            setOpenId(menu.site.id);
            setMenu(null);
          }}
          onCopy={() => {
            copySdk(menu.site);
            setMenu(null);
          }}
          onCheck={() => {
            checkSite.mutate(menu.site.id);
            setMenu(null);
          }}
          onDisable={() => {
            setConfirm({ site: menu.site, type: 'disable' });
            setMenu(null);
          }}
          onEnable={() => {
            enableSite.mutate(menu.site.id);
            setMenu(null);
          }}
          onDelete={() => {
            setConfirm({ site: menu.site, type: 'delete' });
            setMenu(null);
          }}
        />
      )}

      {addOpen && (
        <AddSiteModal
          pending={createSite.isPending}
          error={addError}
          onClose={() => setAddOpen(false)}
          onSubmit={(payload) => createSite.mutate(payload)}
        />
      )}

      {openId != null && (
        <SiteDrawer
          siteId={openId}
          onClose={() => setOpenId(null)}
          onDisable={() => {
            const site = sites.find((item) => item.id === openId);
            if (site) setConfirm({ site, type: 'disable' });
          }}
          onDelete={(site) => setConfirm({ site, type: 'delete' })}
        />
      )}

      {confirm?.type === 'disable' && (
        <ConfirmDialog
          title="Отключить сайт"
          confirmLabel="Отключить"
          pending={disableSite.isPending}
          onClose={() => setConfirm(null)}
          onConfirm={() => disableSite.mutate(confirm.site.id)}
        >
          <p>Сайт перестанет считаться активным для web tracking. Исторические данные сохраняются.</p>
        </ConfirmDialog>
      )}
      {confirm?.type === 'delete' && (
        <ConfirmDialog
          title="Удалить сайт"
          confirmLabel="Удалить"
          pending={deleteSite.isPending}
          onClose={() => setConfirm(null)}
          onConfirm={() => deleteSite.mutate(confirm.site.id)}
        >
          <p>Сайт можно удалить только если с ним ещё нет истории кликов, событий и ссылок.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}

function SiteRowMenu({
  site,
  rect,
  onClose,
  onOpen,
  onCopy,
  onCheck,
  onDisable,
  onEnable,
  onDelete,
}: {
  site: BusinessSite;
  rect: DOMRect;
  onClose: () => void;
  onOpen: () => void;
  onCopy: () => void;
  onCheck: () => void;
  onDisable: () => void;
  onEnable: () => void;
  onDelete: () => void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const width = 200;
  const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
  const [top, setTop] = useState(rect.bottom + 4);

  useLayoutEffect(() => {
    const el = menuRef.current;
    if (!el) return;
    const height = el.offsetHeight;
    const below = rect.bottom + 4;
    const nextTop = below + height > window.innerHeight - 8 ? rect.top - height - 4 : below;
    setTop(Math.max(8, nextTop));
  }, [rect]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (menuRef.current?.contains(target)) return;
      if (target?.closest(`[data-site-menu-trigger="${site.id}"]`)) return;
      onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onClose, true);
    window.addEventListener('resize', onClose);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onClose, true);
      window.removeEventListener('resize', onClose);
    };
  }, [site.id, onClose]);

  return createPortal(
    <div ref={menuRef} className="fixed z-50 ui-card py-1 w-52 text-sm shadow-soft" style={{ top, left }}>
      <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onOpen}>
        Открыть настройки
      </button>
      <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onCopy}>
        Скопировать SDK
      </button>
      <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onCheck}>
        Проверить подключение
      </button>
      {site.status === 'active' ? (
        <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onDisable}>
          Отключить
        </button>
      ) : (
        <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onEnable}>
          Включить
        </button>
      )}
      {site.can_delete && (
        <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onDelete}>
          Удалить
        </button>
      )}
    </div>,
    document.body,
  );
}
