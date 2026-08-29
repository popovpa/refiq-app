import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Copy, ExternalLink, MoreVertical, Plus } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { EmptyState } from '@/shared/components/EmptyState';
import { Button } from '@/shared/components/Button';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { useToast } from '@/shared/components/Toast';
import { formatNumber } from '@/shared/utils/format';
import { GetLinkModal } from '@/shared/offers/GetLinkModal';
import { OfferImage } from '@/shared/offers/OfferImage';
import { trafficLabel } from '@/shared/offers/labels';
import { displayTrackingUrl, partnerQrCodeDownloadPath, publicTrackingUrl } from '@/shared/offers/trackingLink';
import { EditLinkModal } from '@/shared/partner/links/EditLinkModal';
import { LinkDetailDrawer } from '@/shared/partner/links/LinkDetailDrawer';
import {
  formatLinkCr,
  formatLinkEarned,
  formatLinkStatValue,
  isUnnamedLink,
  linkDisplayName,
  linkStatusClass,
  linkStatusLabel,
  LINKS_PERIOD_DAYS,
  type PartnerLinkItem,
  type PartnerLinksResponse,
} from '@/shared/partner/links/types';
import { cn } from '@/shared/utils/cn';

const PER_PAGE = 25;

function stopRowNavigation(event: { stopPropagation: () => void }) {
  event.stopPropagation();
}

export function PartnerLinks() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const initialOfferId = searchParams.get('offerId') || '';
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [offerFilter, setOfferFilter] = useState(initialOfferId);
  const [sourceFilter, setSourceFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedLink, setSelectedLink] = useState<PartnerLinkItem | null>(null);
  const [editLink, setEditLink] = useState<PartnerLinkItem | null>(null);
  const [statusAction, setStatusAction] = useState<{ link: PartnerLinkItem; next: 'ACTIVE' | 'DISABLED' } | null>(
    null,
  );
  const [menuLinkId, setMenuLinkId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, offerFilter, sourceFilter, statusFilter]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(PER_PAGE));
    params.set('days', String(LINKS_PERIOD_DAYS));
    if (debouncedSearch) params.set('q', debouncedSearch);
    if (offerFilter) params.set('offer_id', offerFilter);
    if (sourceFilter) params.set('traffic_source', sourceFilter);
    if (statusFilter) params.set('status', statusFilter);
    return `?${params.toString()}`;
  }, [page, debouncedSearch, offerFilter, sourceFilter, statusFilter]);

  const { data, isLoading, isError, refetch } = useQuery<PartnerLinksResponse>({
    queryKey: ['partner', 'links', queryString],
    queryFn: () => api.get(`/partner/links${queryString}`),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'ACTIVE' | 'DISABLED' }) =>
      api.patch<PartnerLinkItem>(`/partner/links/${id}`, { status }),
    onSuccess: (updated, variables) => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'links'] });
      setSelectedLink((current) =>
        current && String(current.id) === String(updated.id) ? { ...current, ...updated } : current,
      );
      addToast(variables.status === 'ACTIVE' ? 'Ссылка активирована' : 'Ссылка отключена', 'success');
      setStatusAction(null);
      setMenuLinkId(null);
    },
    onError: (err: unknown, variables) => {
      const message = (err as ApiError | null)?.error?.message;
      addToast(
        message ||
          (variables.status === 'ACTIVE' ? 'Не удалось активировать ссылку' : 'Не удалось отключить ссылку'),
        'error',
      );
    },
  });

  const copy = async (link: PartnerLinkItem) => {
    await navigator.clipboard.writeText(publicTrackingUrl(link.short_code));
    addToast('Ссылка скопирована', 'success');
  };

  const downloadQr = async (link: PartnerLinkItem) => {
    try {
      await api.download(partnerQrCodeDownloadPath(link.id), `${link.short_code}.png`);
    } catch {
      addToast('Не удалось скачать QR-код', 'error');
    }
  };

  const openPublicLink = (link: PartnerLinkItem) => {
    window.open(publicTrackingUrl(link.short_code), '_blank', 'noopener,noreferrer');
  };

  useEffect(() => {
    if (!menuLinkId) return;
    const handleClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuLinkId(null);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuLinkId]);

  const items = data?.items || [];
  const total = data?.total ?? 0;
  const summary = data?.summary;
  const filterOptions = data?.filter_options;
  const hasAnyLinks = (filterOptions?.offers.length ?? 0) > 0;
  const hasActiveFilters = Boolean(debouncedSearch || offerFilter || sourceFilter || statusFilter);
  const rangeStart = total === 0 ? 0 : (page - 1) * PER_PAGE + 1;
  const rangeEnd = Math.min(page * PER_PAGE, total);
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  const resetFilters = () => {
    setSearch('');
    setDebouncedSearch('');
    setOfferFilter('');
    setSourceFilter('');
    setStatusFilter('');
    setSearchParams({});
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="ui-page-title">Мои ссылки</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus size={16} /> Создать ссылку
        </Button>
      </div>

      {isLoading ? (
        <>
          <Skeleton className="h-20 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </>
      ) : isError ? (
        <div className="ui-card p-5 space-y-3">
          <p className="text-sm text-muted-foreground">Не удалось загрузить ссылки.</p>
          <Button variant="secondary" onClick={() => refetch()}>
            Повторить
          </Button>
        </div>
      ) : !hasAnyLinks && !hasActiveFilters ? (
        <div className="space-y-3">
          <EmptyState
            title="У вас пока нет партнёрских ссылок"
            description="Выберите оффер и создайте первую ссылку, чтобы начать продвижение."
            action={{ label: 'Создать ссылку', onClick: () => setCreateOpen(true) }}
          />
          <button
            type="button"
            className="text-sm text-primary hover:underline"
            onClick={() => navigate('/partner/offers')}
          >
            Открыть офферы →
          </button>
        </div>
      ) : (
        <>
          {summary && (
            <div className="ui-card p-4">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <Kpi label="Активные ссылки" value={formatNumber(summary.active_links)} />
                <Kpi label="Клики" value={formatNumber(summary.clicks)} />
                <Kpi label="Конверсии" value={formatNumber(summary.conversions)} />
                <Kpi label="Заработано" value={`${formatNumber(summary.earned)} ₽`} />
              </div>
            </div>
          )}

          <div className="flex flex-col lg:flex-row gap-2">
            <input
              className="ui-input flex-1 h-9"
              placeholder="Поиск по названию или ссылке..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              className="ui-input w-full lg:w-auto h-9"
              value={offerFilter}
              onChange={(e) => {
                setOfferFilter(e.target.value);
                if (e.target.value) {
                  setSearchParams({ offerId: e.target.value });
                } else {
                  setSearchParams({});
                }
              }}
            >
              <option value="">Все офферы</option>
              {(filterOptions?.offers || []).map((offer) => (
                <option key={offer.id} value={String(offer.id)}>
                  {offer.name}
                </option>
              ))}
            </select>
            <select
              className="ui-input w-full lg:w-auto h-9"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="">Все источники</option>
              {(filterOptions?.traffic_sources || []).map((source) => (
                <option key={source} value={source}>
                  {trafficLabel(source)}
                </option>
              ))}
            </select>
            <select
              className="ui-input w-full lg:w-auto h-9"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">Все статусы</option>
              <option value="ACTIVE">Активна</option>
              <option value="DISABLED">Отключена</option>
            </select>
          </div>

          {!items.length ? (
            <EmptyState
              title="Ссылки не найдены"
              description="Попробуйте изменить поиск или параметры фильтрации."
              action={{ label: 'Сбросить фильтры', onClick: resetFilters }}
            />
          ) : (
            <div className="ui-card overflow-x-auto">
              <table className="ui-table">
                <thead>
                  <tr>
                    <th>Оффер</th>
                    <th>Название</th>
                    <th className="hidden md:table-cell">Ссылка</th>
                    <th className="hidden lg:table-cell">Источник</th>
                    <th className="hidden xl:table-cell text-right">Клики</th>
                    <th className="hidden xl:table-cell text-right">Конв.</th>
                    <th className="hidden xl:table-cell text-right">CR</th>
                    <th className="hidden xl:table-cell text-right">Заработано</th>
                    <th>Статус</th>
                    <th className="text-right">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((link) => (
                    <tr
                      key={link.id}
                      className="cursor-pointer"
                      onClick={() => setSelectedLink(link)}
                    >
                      <td onClick={stopRowNavigation}>
                        <button
                          type="button"
                          className="flex items-center gap-2.5 text-left min-w-0"
                          onClick={() => navigate(`/partner/offers/${link.offer_id}`)}
                        >
                          <OfferImage src={link.offer_image_url} name={link.offer_name || 'Оффер'} size="sm" />
                          <span className="font-medium text-primary hover:underline truncate max-w-[140px]">
                            {link.offer_name || 'Оффер'}
                          </span>
                        </button>
                      </td>
                      <td>
                        <span className={cn(isUnnamedLink(link.name) && 'text-muted-foreground')}>
                          {linkDisplayName(link.name)}
                        </span>
                      </td>
                      <td className="hidden md:table-cell">
                        <code className="text-xs bg-muted px-2 py-1 rounded-md whitespace-nowrap">
                          {displayTrackingUrl(link.short_code)}
                        </code>
                      </td>
                      <td className="hidden lg:table-cell">
                        {link.traffic_source ? (
                          trafficLabel(link.traffic_source)
                        ) : (
                          <span className="text-muted-foreground">Не указан</span>
                        )}
                      </td>
                      <td className="hidden xl:table-cell text-right tabular-nums">
                        {formatLinkStatValue(link.stats?.clicks, link.stats?.has_stat_data ?? false, (v) =>
                          formatNumber(v),
                        )}
                      </td>
                      <td className="hidden xl:table-cell text-right tabular-nums">
                        {formatLinkStatValue(link.stats?.conversions, link.stats?.has_stat_data ?? false, (v) =>
                          formatNumber(v),
                        )}
                      </td>
                      <td className="hidden xl:table-cell text-right tabular-nums">{formatLinkCr(link.stats)}</td>
                      <td className="hidden xl:table-cell text-right tabular-nums">{formatLinkEarned(link.stats)}</td>
                      <td>
                        <span className={cn('ui-badge', linkStatusClass(link.status))}>
                          {linkStatusLabel(link.status)}
                        </span>
                      </td>
                      <td className="text-right" onClick={stopRowNavigation}>
                        <div className="inline-flex items-center gap-0.5 relative">
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label="Скопировать ссылку"
                            onClick={() => copy(link)}
                          >
                            <Copy size={14} />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label="Открыть ссылку"
                            onClick={() => openPublicLink(link)}
                          >
                            <ExternalLink size={14} />
                          </Button>
                          <div className="relative" ref={menuLinkId === String(link.id) ? menuRef : undefined}>
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label="Меню действий"
                              onClick={() =>
                                setMenuLinkId((current) => (current === String(link.id) ? null : String(link.id)))
                              }
                            >
                              <MoreVertical size={14} />
                            </Button>
                            {menuLinkId === String(link.id) && (
                              <div className="absolute right-0 top-full mt-1 z-20 ui-card py-1 min-w-[168px] shadow-soft">
                                <MenuButton
                                  onClick={() => {
                                    setSelectedLink(link);
                                    setMenuLinkId(null);
                                  }}
                                >
                                  Открыть детали
                                </MenuButton>
                                <MenuButton
                                  onClick={() => {
                                    setEditLink(link);
                                    setMenuLinkId(null);
                                  }}
                                >
                                  Редактировать
                                </MenuButton>
                                <MenuButton
                                  onClick={() => {
                                    setMenuLinkId(null);
                                    void downloadQr(link);
                                  }}
                                >
                                  Скачать QR-код
                                </MenuButton>
                                {link.status === 'ACTIVE' ? (
                                  <>
                                    <div className="my-1 border-t border-border/70" />
                                    <MenuButton
                                      destructive
                                      onClick={() => {
                                        setStatusAction({ link, next: 'DISABLED' });
                                        setMenuLinkId(null);
                                      }}
                                    >
                                      Отключить
                                    </MenuButton>
                                  </>
                                ) : (
                                  <>
                                    <div className="my-1 border-t border-border/70" />
                                    <MenuButton
                                      onClick={() => {
                                        setStatusAction({ link, next: 'ACTIVE' });
                                        setMenuLinkId(null);
                                      }}
                                    >
                                      Активировать
                                    </MenuButton>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="px-4 py-3 border-t border-border/70 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <p className="text-xs text-muted-foreground">
                  Показано {formatNumber(rangeStart)}–{formatNumber(rangeEnd)} из {formatNumber(total)}
                </p>
                {totalPages > 1 && (
                  <div className="inline-flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      ‹
                    </Button>
                    <span className="text-xs text-muted-foreground px-2">
                      {page} / {totalPages}
                    </span>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    >
                      ›
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}

        </>
      )}

      {createOpen && <GetLinkModal onClose={() => setCreateOpen(false)} />}

      {selectedLink && !editLink && (
        <LinkDetailDrawer
          link={selectedLink}
          onClose={() => setSelectedLink(null)}
          onEdit={() => setEditLink(selectedLink)}
          onCopy={() => copy(selectedLink)}
          statusPending={statusMutation.isPending}
          onRequestActivate={() => setStatusAction({ link: selectedLink, next: 'ACTIVE' })}
          onRequestDisable={() => setStatusAction({ link: selectedLink, next: 'DISABLED' })}
        />
      )}

      {editLink && <EditLinkModal link={editLink} onClose={() => setEditLink(null)} />}

      {statusAction && (
        <ConfirmDialog
          title={statusAction.next === 'ACTIVE' ? 'Активировать ссылку?' : 'Отключить ссылку?'}
          confirmLabel={statusAction.next === 'ACTIVE' ? 'Активировать' : 'Отключить'}
          pending={statusMutation.isPending}
          onClose={() => {
            if (!statusMutation.isPending) setStatusAction(null);
          }}
          onConfirm={() => {
            if (statusMutation.isPending) return;
            statusMutation.mutate({ id: String(statusAction.link.id), status: statusAction.next });
          }}
        >
          <p className="font-medium text-foreground">
            {[statusAction.link.offer_name, linkDisplayName(statusAction.link.name)].filter(Boolean).join(' — ')}
          </p>
          <p>{displayTrackingUrl(statusAction.link.short_code)}</p>
          {statusAction.next === 'ACTIVE' ? (
            <p>После активации ссылка снова начнёт принимать новый трафик.</p>
          ) : (
            <>
              <p>После отключения ссылка перестанет принимать новый трафик.</p>
              <p>Исторические клики, конверсии и статистика сохранятся.</p>
            </>
          )}
        </ConfirmDialog>
      )}
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tracking-tight mt-0.5">{value}</p>
    </div>
  );
}

function MenuButton({
  children,
  onClick,
  destructive = false,
}: {
  children: ReactNode;
  onClick: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      type="button"
      className={cn(
        'w-full text-left px-3 py-2 text-sm hover:bg-muted/60',
        destructive ? 'text-destructive' : 'text-foreground',
      )}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
