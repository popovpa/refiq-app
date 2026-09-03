import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { useToast } from '@/shared/components/Toast';
import { aiErrorMessage } from '@/shared/ai/messages';
import type { BusinessPromotionLink } from '@/shared/links/BusinessLinkDetailDrawer';
import { trafficLabel } from '@/shared/offers/labels';
import { displayTrackingUrl } from '@/shared/offers/trackingLink';
import { cn } from '@/shared/utils/cn';
import {
  allEnabledSelected,
  emptySelection,
  hasSelection,
  isKitSubmitValid,
  kitRequestPayload,
  matchesLinkQuery,
  qrSelected,
  recommendedSelection,
  selectAllSlots,
  selectNoneSlots,
  setQrTrackingLink,
  syncQrLink,
  toggleSlot,
  type KitSelection,
} from './kitSelection';
import { PromoImageGallery } from './PromoImageGallery';
import { PromoTextList, type TextEditDraft } from './PromoTextList';
import { GenerationProgressPanel } from './GenerationProgressPanel';
import type {
  Creative,
  PromoCatalogItem,
  PromoGenerationItem,
  PromoGenerationRun,
} from './types';

const ACTIVE_RUN = new Set(['queued', 'running', 'cancel_requested']);
const TERMINAL_RUN = new Set(['completed', 'completed_with_errors', 'cancelled', 'failed']);

export function OfferCreativesTab({
  offerId,
  variant = 'full',
  onCreateTrackingLink,
}: {
  offerId: string;
  variant?: 'full' | 'banner';
  onCreateTrackingLink?: () => void;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [kitOpen, setKitOpen] = useState(false);
  const [forceSelection, setForceSelection] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [selection, setSelection] = useState<KitSelection>(emptySelection());
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelPending, setCancelPending] = useState(false);
  const [seenTerminal, setSeenTerminal] = useState(false);

  const { data, isLoading } = useQuery<{ items: Creative[] }>({
    queryKey: ['business', 'offers', offerId, 'creatives'],
    queryFn: () => api.get(`/business/offers/${offerId}/creatives`),
    enabled: variant === 'full',
  });

  const catalogQuery = useQuery<{ items: PromoCatalogItem[]; recommended: string[] }>({
    queryKey: ['business', 'offers', offerId, 'promo-catalog'],
    queryFn: () => api.get(`/business/offers/${offerId}/promo-generation-catalog`),
    enabled: kitOpen || variant === 'full',
  });

  const offerQuery = useQuery<{ promotion_links?: BusinessPromotionLink[] }>({
    queryKey: ['business', 'offers', offerId],
    queryFn: () => api.get(`/business/offers/${offerId}`),
    enabled: kitOpen || variant === 'full',
  });
  const ownLinksQuery = useQuery<{ items: Array<{
    id: number;
    name?: string | null;
    url: string;
    short_code: string;
    destination_url: string;
    status: string;
    stats?: { clicks: number; conversions: number };
  }> }>({
    queryKey: ['business', 'offers', offerId, 'own-links'],
    queryFn: () => api.get(`/business/offers/${offerId}/links`),
    enabled: kitOpen || variant === 'full',
  });

  const activeQuery = useQuery<{ run: PromoGenerationRun | null }>({
    queryKey: ['business', 'offers', offerId, 'promo-generation-active'],
    queryFn: () => api.get(`/business/offers/${offerId}/promo-generation-runs/active`),
    refetchInterval: (query) => {
      const status = query.state.data?.run?.status;
      return status && ACTIVE_RUN.has(status) ? 1500 : false;
    },
  });

  const run = activeQuery.data?.run || null;
  const runActive = !!run && ACTIVE_RUN.has(run.status);

  const runQuery = useQuery<PromoGenerationRun>({
    queryKey: ['business', 'offers', offerId, 'promo-generation-run', run?.id],
    queryFn: () => api.get(`/business/offers/${offerId}/promo-generation-runs/${run?.id}`),
    enabled: kitOpen && !!run?.id,
    refetchInterval: runActive ? 1500 : false,
  });

  const liveRun = runQuery.data || run;
  const runSignature = liveRun
    ? `${liveRun.status}:${liveRun.completed_items}:${liveRun.created_ids?.length || 0}:${liveRun.items
        .map((item) => `${item.id}:${item.status}:${item.material_ids?.length || 0}`)
        .join(',')}`
    : '';
  const catalog = catalogQuery.data?.items || [];
  const recommended =
    catalogQuery.data?.recommended || catalog.filter((item) => item.recommended).map((item) => item.id);
  const promoLinks = [
    ...(offerQuery.data?.promotion_links || []),
    ...(ownLinksQuery.data?.items || []).map((link) => ({
      id: link.id,
      name: link.name || 'Своя ссылка',
      url: link.url,
      short_code: link.short_code,
      destination_url: link.destination_url,
      partner_name: 'Свой трафик',
      status: link.status,
      clicks: link.stats?.clicks || 0,
      conversions: link.stats?.conversions || 0,
    })),
  ];

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'creatives'] });
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'promo-generation-active'] });
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId] });
  };

  useEffect(() => {
    if (!liveRun) return;
    if (ACTIVE_RUN.has(liveRun.status) || (TERMINAL_RUN.has(liveRun.status) && !seenTerminal)) {
      queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'creatives'] });
    }
  }, [runSignature]);

  const openKitSelection = () => {
    setForceSelection(true);
    setKitOpen(true);
    setSelection(syncQrLink(recommendedSelection(recommended), promoLinks));
  };

  const openKitDetails = () => {
    setForceSelection(false);
    setKitOpen(true);
  };

  const startKit = async () => {
    try {
      const result = await api.post<PromoGenerationRun>(
        `/business/offers/${offerId}/creatives/promo-kit`,
        kitRequestPayload(selection),
      );
      setSeenTerminal(false);
      setForceSelection(false);
      queryClient.setQueryData(['business', 'offers', offerId, 'promo-generation-active'], { run: result });
      queryClient.setQueryData(['business', 'offers', offerId, 'promo-generation-run', result.id], result);
    } catch (err) {
      addToast(aiErrorMessage(err, 'Не удалось запустить генерацию'), 'error');
    }
  };

  const cancelRun = async () => {
    if (!liveRun) return;
    setCancelPending(true);
    try {
      const result = await api.post<PromoGenerationRun>(
        `/business/offers/${offerId}/promo-generation-runs/${liveRun.id}/cancel`
      );
      queryClient.setQueryData(['business', 'offers', offerId, 'promo-generation-active'], { run: result });
      queryClient.setQueryData(['business', 'offers', offerId, 'promo-generation-run', result.id], result);
      setCancelOpen(false);
    } catch (err) {
      addToast(aiErrorMessage(err, 'Не удалось остановить генерацию'), 'error');
    } finally {
      setCancelPending(false);
    }
  };

  const ackRun = async () => {
    if (!liveRun) return;
    try {
      await api.post(`/business/offers/${offerId}/promo-generation-runs/${liveRun.id}/ack`);
      queryClient.setQueryData(['business', 'offers', offerId, 'promo-generation-active'], { run: null });
      setKitOpen(false);
      setSeenTerminal(true);
    } catch (err) {
      addToast(aiErrorMessage(err, 'Не удалось закрыть статус'), 'error');
    }
    invalidate();
  };

  const retryItem = async (item: PromoGenerationItem) => {
    if (!liveRun) return;
    try {
      const result = await api.post<PromoGenerationRun>(
        `/business/offers/${offerId}/promo-generation-runs/${liveRun.id}/items/${item.id}/retry`
      );
      queryClient.setQueryData(['business', 'offers', offerId, 'promo-generation-active'], { run: result });
      queryClient.setQueryData(['business', 'offers', offerId, 'promo-generation-run', result.id], result);
    } catch (err) {
      addToast(aiErrorMessage(err, 'Не удалось повторить пункт'), 'error');
    }
  };

  const retryFailed = async () => {
    if (!liveRun) return;
    setForceSelection(false);
    const items = liveRun.items.filter((entry) => entry.status === 'failed' || entry.status === 'cancelled');
    for (const item of items) {
      await retryItem(item);
    }
  };

  const publish = useMutation({
    mutationFn: (id: number) => api.post(`/business/offers/${offerId}/creatives/${id}/publish`),
    onSuccess: () => {
      invalidate();
      addToast('Материал опубликован', 'success');
    },
    onError: (err) => addToast(aiErrorMessage(err, 'Не удалось опубликовать'), 'error'),
  });

  const unpublish = useMutation({
    mutationFn: (id: number) => api.post(`/business/offers/${offerId}/creatives/${id}/unpublish`),
    onSuccess: () => {
      invalidate();
      addToast('Материал возвращён в черновик', 'success');
    },
    onError: (err) => addToast(aiErrorMessage(err, 'Не удалось снять с публикации'), 'error'),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/business/offers/${offerId}/creatives/${id}`),
    onSuccess: () => {
      invalidate();
      addToast('Материал удалён', 'success');
    },
    onError: (err) => addToast(aiErrorMessage(err, 'Не удалось удалить'), 'error'),
  });

  const saveEdit = useMutation({
    mutationFn: ({ id, draft }: { id: number; draft: TextEditDraft }) =>
      api.patch(`/business/offers/${offerId}/creatives/${id}`, {
        headline: draft.headline,
        body: draft.body,
        cta: draft.cta,
      }),
    onSuccess: () => {
      invalidate();
      addToast('Текст сохранён', 'success');
    },
    onError: (err) => addToast(aiErrorMessage(err, 'Не удалось сохранить'), 'error'),
  });

  const items = data?.items || [];
  const texts = items.filter((item) => item.type !== 'banner');
  const images = items.filter((item) => item.type === 'banner');
  const modalPhase = forceSelection && !runActive ? 'selection' : modalState(liveRun);
  const showBanner = !!liveRun && !seenTerminal;
  const showMaterials = items.length > 0 || showBanner;

  const copyText = async (value: string) => {
    await navigator.clipboard.writeText(value);
    addToast('Текст скопирован', 'success');
  };

  const downloadImage = async (item: Creative) => {
    try {
      await api.download(`/business/offers/${offerId}/promo-materials/${item.id}/image`, `promo-${item.id}.png`);
    } catch (err) {
      addToast(aiErrorMessage(err, 'Не удалось скачать изображение'), 'error');
    }
  };

  const regenerate = async (item: Creative) => {
    setBusyId(item.id);
    try {
      await api.post(`/business/offers/${offerId}/creatives/${item.id}/regenerate`);
      invalidate();
      addToast('Материал обновлён', 'success');
    } catch (err) {
      addToast(aiErrorMessage(err, 'Не удалось перегенерировать'), 'error');
    } finally {
      setBusyId(null);
    }
  };

  const toggle = (id: string) => {
    setSelection((prev) => toggleSlot(prev, id, promoLinks));
  };

  if (variant === 'banner') {
    return (
      <>
        {showBanner && liveRun && (
          <GenerationProgressPanel
            run={liveRun}
            onDetails={openKitDetails}
            onStop={() => setCancelOpen(true)}
            onView={() => ackRun()}
            onRetryFailed={retryFailed}
          />
        )}
        {kitOpen && (
          <KitModal
            phase={modalPhase}
            catalog={catalog}
            selected={selection}
            links={promoLinks}
            run={liveRun}
            onClose={() => setKitOpen(false)}
            onToggle={toggle}
            onAll={() => setSelection(selectAllSlots(catalog.map((item) => item.id), promoLinks))}
            onNone={() => setSelection(selectNoneSlots())}
            onQrLinkChange={(id) => setSelection((prev) => setQrTrackingLink(prev, id))}
            onCreateLink={onCreateTrackingLink}
            onCreate={startKit}
            onStop={() => setCancelOpen(true)}
            onRetry={retryItem}
            onRetryFailed={retryFailed}
            onCreateMore={openKitSelection}
            onView={ackRun}
          />
        )}
        {cancelOpen && (
          <ConfirmDialog
            title="Остановить генерацию?"
            confirmLabel="Остановить"
            cancelLabel="Продолжить генерацию"
            confirmVariant="destructive"
            pending={cancelPending}
            onClose={() => setCancelOpen(false)}
            onConfirm={cancelRun}
          >
            Уже созданные материалы сохранятся. Ожидающие материалы созданы не будут.
          </ConfirmDialog>
        )}
      </>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="ui-section-title">Материалы для продвижения</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Черновики видите только вы. После публикации материалы станут доступны партнёрам оффера.
        </p>
      </div>

      {showBanner && liveRun && (
        <GenerationProgressPanel
          run={liveRun}
          onDetails={openKitDetails}
          onStop={() => setCancelOpen(true)}
          onView={() => ackRun()}
          onRetryFailed={retryFailed}
        />
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Загрузка…</p>
      ) : !showMaterials ? (
        <div className="ui-card p-8 flex flex-col items-center text-center gap-3">
          <h3 className="text-base font-medium">Подготовьте оффер к продвижению</h3>
          <p className="text-sm text-muted-foreground max-w-md">
            AI создаст готовые тексты и изображения на основе данных оффера.
          </p>
          <Button onClick={openKitSelection} disabled={runActive}>
            Создать материалы с AI
          </Button>
        </div>
      ) : (
        <div className="space-y-5">
          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-medium">Изображения</h3>
              <Button size="sm" variant="ghost" onClick={openKitSelection} disabled={runActive}>
                <Plus size={14} />
                Создать ещё
              </Button>
            </div>
            <PromoImageGallery
              images={images}
              run={liveRun}
              showRunPlaceholders={showBanner}
              busyId={busyId}
              publishPending={publish.isPending}
              onPublish={(item) => publish.mutate(item.id)}
              onUnpublish={(item) => unpublish.mutate(item.id)}
              onDownload={downloadImage}
              onRegenerate={regenerate}
              onDelete={(item) => remove.mutate(item.id)}
              onRetry={retryItem}
            />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-medium">Тексты</h3>
              <Button size="sm" variant="ghost" onClick={openKitSelection} disabled={runActive}>
                <Plus size={14} />
                Сгенерировать ещё
              </Button>
            </div>
            <PromoTextList
              texts={texts}
              run={liveRun}
              showRunPlaceholders={showBanner}
              busyId={busyId}
              publishPending={publish.isPending}
              savePending={saveEdit.isPending}
              onCopy={copyText}
              onPublish={(item) => publish.mutate(item.id)}
              onUnpublish={(item) => unpublish.mutate(item.id)}
              onRegenerate={regenerate}
              onDelete={(item) => remove.mutate(item.id)}
              onRetry={retryItem}
              onSave={async (item, draft) => {
                await saveEdit.mutateAsync({ id: item.id, draft });
              }}
            />
          </section>
        </div>
      )}

      {kitOpen && (
        <KitModal
          phase={modalPhase}
          catalog={catalog}
          selected={selection}
          links={promoLinks}
          run={liveRun}
          onClose={() => setKitOpen(false)}
          onToggle={toggle}
          onAll={() => setSelection(selectAllSlots(catalog.map((item) => item.id), promoLinks))}
          onNone={() => setSelection(selectNoneSlots())}
          onQrLinkChange={(id) => setSelection((prev) => setQrTrackingLink(prev, id))}
          onCreateLink={onCreateTrackingLink}
          onCreate={startKit}
          onStop={() => setCancelOpen(true)}
          onRetry={retryItem}
          onRetryFailed={retryFailed}
          onCreateMore={openKitSelection}
          onView={ackRun}
        />
      )}

      {cancelOpen && (
        <ConfirmDialog
          title="Остановить генерацию?"
          confirmLabel="Остановить"
          cancelLabel="Продолжить генерацию"
          confirmVariant="destructive"
          pending={cancelPending}
          onClose={() => setCancelOpen(false)}
          onConfirm={cancelRun}
        >
          Уже созданные материалы сохранятся. Ожидающие материалы созданы не будут.
        </ConfirmDialog>
      )}
    </div>
  );
}

function modalState(run: PromoGenerationRun | null): 'selection' | 'generation' | 'result' {
  if (!run) return 'selection';
  if (ACTIVE_RUN.has(run.status)) return 'generation';
  return 'result';
}

function KitModal({
  phase,
  catalog,
  selected,
  links,
  run,
  onClose,
  onToggle,
  onAll,
  onNone,
  onQrLinkChange,
  onCreateLink,
  onCreate,
  onStop,
  onRetry,
  onRetryFailed,
  onCreateMore,
  onView,
}: {
  phase: 'selection' | 'generation' | 'result';
  catalog: PromoCatalogItem[];
  selected: KitSelection;
  links: BusinessPromotionLink[];
  run: PromoGenerationRun | null;
  onClose: () => void;
  onToggle: (id: string) => void;
  onAll: () => void;
  onNone: () => void;
  onQrLinkChange: (id: string | null) => void;
  onCreateLink?: () => void;
  onCreate: () => void;
  onStop: () => void;
  onRetry: (item: PromoGenerationItem) => void;
  onRetryFailed: () => void;
  onCreateMore: () => void;
  onView: () => void;
}) {
  const textSlots = catalog.filter((item) => item.group === 'text');
  const imageSlots = catalog.filter((item) => item.group === 'image');
  const catalogIds = catalog.map((item) => item.id);
  const failed = run?.items.filter((item) => item.status === 'failed').length || 0;
  const cancelled = run?.items.filter((item) => item.status === 'cancelled').length || 0;
  const retryable = failed + cancelled;
  const canSubmit = isKitSubmitValid(selected);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/30">
      <div className="ui-card w-full max-w-lg max-h-[88vh] flex flex-col shadow-soft" role="dialog" aria-modal="true">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border/70 shrink-0">
          <h3 className="ui-section-title">
            {phase === 'selection' ? 'Набор материалов' : phase === 'generation' ? 'Материалы создаются' : 'Результат'}
          </h3>
          <button type="button" className="text-sm text-muted-foreground hover:text-foreground" onClick={onClose}>
            Закрыть
          </button>
        </div>
        <div className="overflow-auto p-5 space-y-4">
          {phase === 'selection' && (
            <>
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm text-muted-foreground">Выберите материалы, которые нужно создать.</p>
                <div className="flex items-center gap-3 shrink-0">
                  <button
                    type="button"
                    className="text-xs font-medium text-primary hover:underline disabled:text-muted-foreground disabled:no-underline disabled:cursor-default"
                    onClick={onAll}
                    disabled={allEnabledSelected(selected, catalogIds)}
                  >
                    Выбрать всё
                  </button>
                  <button
                    type="button"
                    className="text-xs font-medium text-muted-foreground hover:text-foreground disabled:opacity-40 disabled:cursor-default"
                    onClick={onNone}
                    disabled={!hasSelection(selected)}
                  >
                    Снять всё
                  </button>
                </div>
              </div>
              <ChipGroup title="Тексты" items={textSlots} selected={selected} onToggle={onToggle} />
              <div className="space-y-2.5">
                <ChipGroup title="Изображения" items={imageSlots} selected={selected} onToggle={onToggle} />
                {qrSelected(selected) ? (
                  <QrLinkPicker
                    links={links}
                    value={selected.qrTrackingLinkId}
                    onChange={onQrLinkChange}
                    onCreateLink={onCreateLink}
                  />
                ) : null}
              </div>
            </>
          )}
          {phase !== 'selection' && run && (
            <>
              <ItemProgressList items={run.items} onRetry={onRetry} />
              <p className="text-sm text-muted-foreground">
                {run.completed_items} из {run.total_items} готово · {run.percentage}%
              </p>
              {phase === 'result' && failed > 0 && (
                <p className="text-sm">Создано {run.completed_items} из {run.total_items} материалов</p>
              )}
            </>
          )}
        </div>
        <div className="px-5 py-4 border-t border-border/70 flex justify-end gap-2 shrink-0">
          {phase === 'selection' && (
            <>
              <Button variant="ghost" onClick={onClose}>
                Отмена
              </Button>
              <Button onClick={onCreate} disabled={!canSubmit}>
                Создать с AI
              </Button>
            </>
          )}
          {phase === 'generation' && !(run?.status === 'cancel_requested' || run?.cancel_requested) && (
            <Button variant="secondary" onClick={onStop}>
              Остановить
            </Button>
          )}
          {phase === 'generation' && (run?.status === 'cancel_requested' || run?.cancel_requested) && (
            <Button variant="ghost" disabled>
              Останавливаем…
            </Button>
          )}
          {phase === 'result' && (
            <>
              {retryable > 0 && (
                <Button variant="secondary" onClick={onRetryFailed}>
                  {run?.completed_items === 0 ? 'Запустить заново' : `Повторить ${retryable}`}
                </Button>
              )}
              {(cancelled > 0 || failed > 0) && (
                <Button variant="secondary" onClick={onCreateMore}>
                  Выбрать материалы
                </Button>
              )}
              <Button onClick={onView}>Посмотреть материалы</Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const IMAGE_CHIP_LABELS: Record<string, string> = {
  images_1_1: '1:1',
  images_16_9: '16:9',
  images_9_16: '9:16',
  images_qr: 'С QR-кодом',
};

function ChipGroup({
  title,
  items,
  selected,
  onToggle,
}: {
  title: string;
  items: PromoCatalogItem[];
  selected: KitSelection;
  onToggle: (id: string) => void;
}) {
  return (
    <div>
      <h4 className="text-[13px] font-medium text-muted-foreground mb-2">{title}</h4>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => {
          const checked = selected.selected.includes(item.id);
          return (
            <button
              key={item.id}
              type="button"
              aria-pressed={checked}
              onClick={() => onToggle(item.id)}
              className={cn(
                'h-8 px-3 rounded-md text-sm font-medium border transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
                checked
                  ? 'border-primary/30 bg-accent text-primary'
                  : 'border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted/60',
              )}
            >
              {IMAGE_CHIP_LABELS[item.id] || item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function QrLinkPicker({
  links,
  value,
  onChange,
  onCreateLink,
}: {
  links: BusinessPromotionLink[];
  value: string | null;
  onChange: (id: string | null) => void;
  onCreateLink?: () => void;
}) {
  const [query, setQuery] = useState('');
  const active = useMemo(
    () => links.filter((link) => String(link.status).toUpperCase() === 'ACTIVE'),
    [links],
  );
  const filtered = useMemo(
    () => active.filter((link) => matchesLinkQuery(link, query)),
    [active, query],
  );

  if (!active.length) {
    return (
      <div className="rounded-md border border-border/70 bg-muted/30 px-3 py-2.5 space-y-2">
        <p className="text-sm">Для QR-кода нужна трекинговая ссылка.</p>
        <p className="text-xs text-muted-foreground">Ссылку создаёт партнёр. После появления она станет доступна здесь.</p>
        {onCreateLink ? (
          <Button size="sm" variant="secondary" onClick={onCreateLink}>
            Создать ссылку
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border/70 bg-muted/30 px-3 py-2.5 space-y-2">
      <p className="text-[13px] font-medium text-muted-foreground">Ссылка для QR-кода</p>
      {active.length > 8 ? (
        <input
          className="ui-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Поиск по названию, каналу или коду"
        />
      ) : null}
      <select
        className="ui-input"
        value={value || ''}
        onChange={(event) => onChange(event.target.value || null)}
      >
        {active.length > 1 && !value ? <option value="">Выберите ссылку</option> : null}
        {filtered.map((link) => (
          <option key={link.id} value={String(link.id)}>
            {qrLinkTitle(link)} · {qrLinkHost(link)}
          </option>
        ))}
      </select>
      {value ? (
        <p className="text-xs text-muted-foreground">{qrLinkHost(active.find((link) => String(link.id) === value))}</p>
      ) : (
        <p className="text-xs text-destructive">Выберите трекинговую ссылку</p>
      )}
    </div>
  );
}

function qrLinkTitle(link: BusinessPromotionLink): string {
  const source = link.traffic_source ? trafficLabel(link.traffic_source) : '';
  const name = link.name || link.partner_name || 'Ссылка';
  return source ? `${source} · ${name}` : name;
}

function qrLinkHost(link?: BusinessPromotionLink): string {
  if (!link) return '';
  if (link.short_code) return displayTrackingUrl(link.short_code);
  return link.url.replace(/^https?:\/\//, '');
}

const ITEM_STATUS_LABELS: Record<PromoGenerationItem['status'], string> = {
  completed: 'Готово',
  generating: 'Генерируется',
  queued: 'Ожидает',
  failed: 'Ошибка',
  cancelled: 'Остановлено',
};

function ItemProgressList({
  items,
  onRetry,
}: {
  items: PromoGenerationItem[];
  onRetry: (item: PromoGenerationItem) => void;
}) {
  return (
    <ul className="space-y-1.5 text-sm">
      {items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-2">
          <span className="min-w-0 truncate">{item.label}</span>
          <span className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-muted-foreground">{ITEM_STATUS_LABELS[item.status]}</span>
            {item.status === 'failed' || item.status === 'cancelled' ? (
              <button type="button" className="text-xs text-primary hover:underline" onClick={() => onRetry(item)}>
                Повторить
              </button>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}
