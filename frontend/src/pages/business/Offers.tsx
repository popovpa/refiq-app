import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { MoreHorizontal } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { useToast } from '@/shared/components/Toast';
import { cn } from '@/shared/utils/cn';
import { formatCommission, formatNumber } from '@/shared/utils/format';
import { OfferImage } from '@/shared/offers/OfferImage';
import { OfferAiSplitButton } from '@/shared/offers/OfferAiSplitButton';
import {
  ACCESS_OPTIONS,
  CATEGORIES,
  OFFER_STATUSES,
  accessLabel,
  statusBadge,
  tabClass,
} from '@/shared/offers/labels';
import type { OfferListItem } from '@/shared/offers/types';

interface OffersResponse {
  items: OfferListItem[];
  total: number;
}

export function BusinessOffers() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState('all');
  const [q, setQ] = useState('');
  const [access, setAccess] = useState('');
  const [category, setCategory] = useState('');
  const [menu, setMenu] = useState<{ offer: OfferListItem; rect: DOMRect } | null>(null);
  const [confirm, setConfirm] = useState<{ id: string; type: 'pause' | 'resume' | 'archive' } | null>(null);

  const params = useMemo(() => {
    const search = new URLSearchParams();
    if (tab !== 'all') search.set('status', tab);
    if (q.trim()) search.set('q', q.trim());
    if (access) search.set('access_policy', access);
    if (category) search.set('category', category);
    const qs = search.toString();
    return qs ? `?${qs}` : '';
  }, [tab, q, access, category]);

  const { data, isLoading } = useQuery<OffersResponse>({
    queryKey: ['business', 'offers', params],
    queryFn: () => api.get(`/business/offers${params}`),
  });

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.patch(`/business/offers/${id}`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business', 'offers'] });
      addToast('Статус оффера обновлён', 'success');
      setConfirm(null);
    },
    onError: () => addToast('Не удалось изменить статус', 'error'),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="ui-page-title">Офферы</h1>
        <OfferAiSplitButton
          label="Создать с AI"
          onPrimary={() => navigate('/business/offers/new?ai=1')}
          items={[
            {
              id: 'ai',
              label: 'Создать с AI',
              ai: true,
              onSelect: () => navigate('/business/offers/new?ai=1'),
            },
            {
              id: 'manual',
              label: 'Создать вручную',
              onSelect: () => navigate('/business/offers/new'),
            },
          ]}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <input
          className="ui-input max-w-xs h-9"
          placeholder="Поиск..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="ui-input w-auto h-9" value={access} onChange={(e) => setAccess(e.target.value)}>
          <option value="">Доступ</option>
          {ACCESS_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <select className="ui-input w-auto h-9" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Категория</option>
          {CATEGORIES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>

      <div className="flex gap-1 bg-muted rounded-md p-0.5 w-fit">
        {OFFER_STATUSES.map((item) => (
          <button key={item.key} type="button" onClick={() => setTab(item.key)} className={tabClass(tab === item.key)}>
            {item.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : !data?.items?.length ? (
        <EmptyState
          title="Офферов пока нет"
          description="Создайте первый оффер, чтобы партнёры могли начать продвигать ваш продукт."
          action={{ label: 'Создать оффер', onClick: () => navigate('/business/offers/new') }}
        />
      ) : (
        <div className="ui-card overflow-x-auto">
          <table className="ui-table">
            <thead>
              <tr>
                <th>Оффер</th>
                <th>Категория</th>
                <th>Статус</th>
                <th>Доступ</th>
                <th>Комиссия</th>
                <th className="text-right">Партнёры</th>
                <th className="text-right">Конверсии</th>
                <th className="text-right">CR</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((offer) => {
                const status = statusBadge(offer.status);
                return (
                  <tr
                    key={offer.id}
                    onClick={() => navigate(`/business/offers/${offer.id}`)}
                    className="cursor-pointer"
                  >
                    <td>
                      <div className="flex items-center gap-3 min-w-0">
                        <OfferImage src={offer.image_url} name={offer.name} />
                        <span className="font-medium truncate">{offer.name}</span>
                      </div>
                    </td>
                    <td className="text-muted-foreground">{offer.category || '—'}</td>
                    <td>
                      <span className={cn('ui-badge', status.className)}>{status.label}</span>
                    </td>
                    <td>{accessLabel(offer.access_policy)}</td>
                    <td>{formatCommission(offer.commission_rules?.[0])}</td>
                    <td className="text-right">{formatNumber(offer.partners_count)}</td>
                    <td className="text-right">{formatNumber(offer.conversions)}</td>
                    <td className="text-right">{offer.cr != null ? `${formatNumber(offer.cr)}%` : '—'}</td>
                    <td className="text-right" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="sm"
                        variant="ghost"
                        data-offer-menu-trigger={offer.id}
                        onClick={(event) => {
                          const rect = event.currentTarget.getBoundingClientRect();
                          setMenu((current) =>
                            current?.offer.id === offer.id ? null : { offer, rect },
                          );
                        }}
                      >
                        <MoreHorizontal size={16} />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {menu && (
        <OfferRowMenu
          offer={menu.offer}
          rect={menu.rect}
          onClose={() => setMenu(null)}
          onOpen={() => {
            setMenu(null);
            navigate(`/business/offers/${menu.offer.id}`);
          }}
          onEdit={() => {
            setMenu(null);
            navigate(`/business/offers/${menu.offer.id}/edit`);
          }}
          onPause={() => {
            setMenu(null);
            setConfirm({ id: String(menu.offer.id), type: 'pause' });
          }}
          onResume={() => {
            setMenu(null);
            setConfirm({ id: String(menu.offer.id), type: 'resume' });
          }}
          onArchive={() => {
            setMenu(null);
            setConfirm({ id: String(menu.offer.id), type: 'archive' });
          }}
        />
      )}

      {confirm?.type === 'pause' && (
        <ConfirmDialog
          title="Приостановить оффер"
          confirmLabel="Приостановить"
          pending={updateStatus.isPending}
          onClose={() => setConfirm(null)}
          onConfirm={() => updateStatus.mutate({ id: confirm.id, status: 'paused' })}
        >
          <p>Новые партнёры не подключаются, новые ссылки не создаются, новый трафик останавливается.</p>
          <p>Исторические данные сохраняются. Существующие допустимые клики и конверсии продолжают обрабатываться согласно attribution window.</p>
        </ConfirmDialog>
      )}
      {confirm?.type === 'resume' && (
        <ConfirmDialog
          title="Возобновить оффер"
          confirmLabel="Возобновить"
          pending={updateStatus.isPending}
          onClose={() => setConfirm(null)}
          onConfirm={() => updateStatus.mutate({ id: confirm.id, status: 'active' })}
        >
          <p>Оффер снова появится в каталоге, партнёры смогут создавать ссылки, новый трафик будет приниматься.</p>
        </ConfirmDialog>
      )}
      {confirm?.type === 'archive' && (
        <ConfirmDialog
          title="Архивировать оффер"
          confirmLabel="Архивировать"
          pending={updateStatus.isPending}
          onClose={() => setConfirm(null)}
          onConfirm={() => updateStatus.mutate({ id: confirm.id, status: 'archived' })}
        >
          <p>Архивирование не удаляет оффер. Клики, конверсии, партнёры, комиссии, выплаты и история условий сохраняются. Архивный оффер не показывается как активный в каталоге.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}

function OfferRowMenu({
  offer,
  rect,
  onClose,
  onOpen,
  onEdit,
  onPause,
  onResume,
  onArchive,
}: {
  offer: OfferListItem;
  rect: DOMRect;
  onClose: () => void;
  onOpen: () => void;
  onEdit: () => void;
  onPause: () => void;
  onResume: () => void;
  onArchive: () => void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const width = 176;
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
      if (target?.closest(`[data-offer-menu-trigger="${offer.id}"]`)) return;
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
  }, [offer.id, onClose]);

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 ui-card py-1 w-44 text-sm shadow-soft"
      style={{ top, left }}
    >
      <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onOpen}>
        Открыть
      </button>
      <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onEdit}>
        Редактировать
      </button>
      {offer.status === 'paused' ? (
        <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onResume}>
          Возобновить
        </button>
      ) : offer.status === 'active' ? (
        <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onPause}>
          Приостановить
        </button>
      ) : null}
      {offer.status !== 'archived' && (
        <button type="button" className="w-full text-left px-3 py-1.5 hover:bg-muted" onClick={onArchive}>
          Архивировать
        </button>
      )}
    </div>,
    document.body,
  );
}
