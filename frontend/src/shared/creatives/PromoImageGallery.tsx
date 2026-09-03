import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, Circle, Loader2, Maximize2, MoreHorizontal, X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import { FORMAT_LABELS, STATUS_LABELS } from './labels';
import type { Creative, PromoGenerationItem, PromoGenerationRun } from './types';

const IMAGE_SLOT_META: Record<string, { formatLabel: string; count: number; qr: boolean }> = {
  images_1_1: { formatLabel: '1:1', count: 1, qr: false },
  images_16_9: { formatLabel: '16:9', count: 1, qr: false },
  images_9_16: { formatLabel: '9:16', count: 1, qr: false },
  images_qr: { formatLabel: '1:1', count: 1, qr: true },
};

type ImageFilter = 'all' | '1:1' | '4:5' | '16:9' | '9:16' | 'qr';

type GalleryCard =
  | {
      kind: 'ready';
      key: string;
      item: Creative;
      variantIndex: number;
      formatLabel: string;
      qr: boolean;
    }
  | {
      kind: 'generating' | 'queued';
      key: string;
      variantIndex: number;
      formatLabel: string;
      qr: boolean;
    }
  | {
      kind: 'cancelled';
      key: string;
      variantIndex: number;
      formatLabel: string;
      qr: boolean;
      generationItem?: PromoGenerationItem;
    }
  | {
      kind: 'failed';
      key: string;
      variantIndex: number;
      formatLabel: string;
      qr: boolean;
      generationItem: PromoGenerationItem;
    };

interface Props {
  images: Creative[];
  run: PromoGenerationRun | null;
  showRunPlaceholders: boolean;
  busyId: number | null;
  publishPending?: boolean;
  onPublish: (item: Creative) => void;
  onUnpublish: (item: Creative) => void;
  onDownload: (item: Creative) => void;
  onRegenerate: (item: Creative) => void;
  onDelete: (item: Creative) => void;
  onRetry: (item: PromoGenerationItem) => void;
}

export function PromoImageGallery({
  images,
  run,
  showRunPlaceholders,
  busyId,
  publishPending,
  onPublish,
  onUnpublish,
  onDownload,
  onRegenerate,
  onDelete,
  onRetry,
}: Props) {
  const [filter, setFilter] = useState<ImageFilter>('all');
  const [lightbox, setLightbox] = useState<Creative | null>(null);
  const [menu, setMenu] = useState<{ card: Extract<GalleryCard, { kind: 'ready' }>; rect: DOMRect } | null>(null);

  const cards = useMemo(
    () => buildGalleryCards(images, showRunPlaceholders ? run : null),
    [images, run, showRunPlaceholders],
  );
  const filters = useMemo(() => availableFilters(cards), [cards]);
  const visible = cards.filter((card) => matchesFilter(card, filter));

  useEffect(() => {
    if (filter !== 'all' && !filters.some((item) => item.id === filter)) {
      setFilter('all');
    }
  }, [filter, filters]);

  useEffect(() => {
    if (!lightbox) return;
    const next = images.find((item) => item.id === lightbox.id);
    if (!next) {
      setLightbox(null);
      return;
    }
    if (
      next.status !== lightbox.status ||
      next.updated_at !== lightbox.updated_at ||
      next.asset?.url !== lightbox.asset?.url
    ) {
      setLightbox(next);
    }
  }, [images, lightbox]);

  if (!cards.length) {
    return <p className="text-sm text-muted-foreground">Изображений пока нет.</p>;
  }

  return (
    <div className="space-y-3">
      {filters.length > 1 && (
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Фильтр изображений">
          {filters.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={filter === item.id}
              className={cn(
                'h-7 px-2.5 rounded-full text-xs font-medium border transition-colors',
                filter === item.id
                  ? 'border-primary/30 bg-accent text-primary'
                  : 'border-border/80 bg-card text-muted-foreground hover:text-foreground',
              )}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 items-stretch">
        {visible.map((card) => {
          if (card.kind === 'ready') {
            return (
              <ReadyImageCard
                key={card.key}
                card={card}
                busy={busyId === card.item.id}
                publishPending={publishPending}
                menuOpen={menu?.card.key === card.key}
                onOpen={() => setLightbox(card.item)}
                onPublish={() => onPublish(card.item)}
                onDownload={() => onDownload(card.item)}
                onMenu={(rect) =>
                  setMenu((current) => (current?.card.key === card.key ? null : { card, rect }))
                }
              />
            );
          }
          if (card.kind === 'failed') {
            return <FailedCard key={card.key} card={card} onRetry={() => onRetry(card.generationItem)} />;
          }
          if (card.kind === 'cancelled') {
            return (
              <CancelledCard
                key={card.key}
                card={card}
                onRetry={card.generationItem ? () => onRetry(card.generationItem!) : undefined}
              />
            );
          }
          return <PlaceholderCard key={card.key} card={card} />;
        })}
      </div>

      {menu && (
        <ImageOverflowMenu
          card={menu.card}
          rect={menu.rect}
          busy={busyId === menu.card.item.id}
          onClose={() => setMenu(null)}
          onOpen={() => setLightbox(menu.card.item)}
          onDownload={() => onDownload(menu.card.item)}
          onRegenerate={() => onRegenerate(menu.card.item)}
          onUnpublish={() => onUnpublish(menu.card.item)}
          onDelete={() => onDelete(menu.card.item)}
        />
      )}

      {lightbox && (
        <PromoImageLightbox
          item={lightbox}
          variantIndex={variantIndexFor(lightbox, images)}
          busy={busyId === lightbox.id}
          publishPending={publishPending}
          onClose={() => setLightbox(null)}
          onDownload={() => onDownload(lightbox)}
          onRegenerate={() => onRegenerate(lightbox)}
          onPublish={() => onPublish(lightbox)}
          onUnpublish={() => onUnpublish(lightbox)}
        />
      )}
    </div>
  );
}

function CardShell({
  preview,
  title,
  meta,
  badgeKey,
  actions,
  hover = false,
}: {
  preview: ReactNode;
  title: string;
  meta: string;
  badgeKey: string;
  actions?: ReactNode;
  hover?: boolean;
}) {
  const badge = STATUS_LABELS[badgeKey] || STATUS_LABELS.draft;
  return (
    <article
      className={cn(
        'relative ui-card overflow-hidden flex flex-col h-full',
        hover && 'group/card transition-shadow hover:shadow-soft hover:border-border',
      )}
    >
      <div className="relative h-[240px] w-full shrink-0 p-3 bg-muted/40 border-b border-border/70">{preview}</div>
      <div className="flex flex-1 flex-col p-3 min-h-[108px]">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium leading-5 min-w-0">{title}</p>
          <span className={cn('ui-badge shrink-0', badge.className)}>{badge.label}</span>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{meta}</p>
        <div className="mt-auto pt-3 flex items-center gap-1 min-h-[32px]">{actions}</div>
      </div>
    </article>
  );
}

function ReadyImageCard({
  card,
  busy,
  publishPending,
  menuOpen,
  onOpen,
  onPublish,
  onDownload,
  onMenu,
}: {
  card: Extract<GalleryCard, { kind: 'ready' }>;
  busy: boolean;
  publishPending?: boolean;
  menuOpen: boolean;
  onOpen: () => void;
  onPublish: () => void;
  onDownload: () => void;
  onMenu: (rect: DOMRect) => void;
}) {
  const { item, qr, formatLabel, variantIndex } = card;
  const src = creativeImageSrc(item);
  const published = item.status === 'active';
  const title = imageTitle(qr);
  const meta = imageMeta({
    variantIndex,
    formatLabel,
    width: item.asset?.width,
    height: item.asset?.height,
  });

  return (
    <CardShell
      hover
      title={title}
      meta={meta}
      badgeKey={item.status}
      preview={
        <button
          type="button"
          className={cn(
            'absolute inset-0 p-3 text-left',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/30',
            src ? 'cursor-pointer' : 'cursor-default',
          )}
          onClick={() => src && onOpen()}
          disabled={!src}
          aria-label={src ? `Открыть ${title}, ${meta}` : title}
        >
          {src ? (
            <img src={src} alt={`${title}, ${meta}`} loading="lazy" className="h-full w-full object-contain" />
          ) : (
            <span className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Изображение ещё не готово.
            </span>
          )}
          {src && (
            <span className="absolute bottom-2 right-2 rounded-md bg-card/90 p-1 text-muted-foreground opacity-0 transition-opacity group-hover/card:opacity-100 group-focus-within/card:opacity-100">
              <Maximize2 size={14} />
            </span>
          )}
          {busy && (
            <span className="absolute inset-0 flex items-center justify-center bg-card/60">
              <Loader2 size={20} className="animate-spin text-primary" />
            </span>
          )}
        </button>
      }
      actions={
        <>
          {item.status === 'draft' ? (
            <Button size="sm" className="flex-1" disabled={publishPending || busy} onClick={onPublish}>
              Опубликовать
            </Button>
          ) : published && src ? (
            <Button size="sm" variant="secondary" className="flex-1" disabled={busy} onClick={onDownload}>
              Скачать
            </Button>
          ) : (
            <span className="flex-1" />
          )}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="px-2"
            aria-label="Действия"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            data-promo-image-menu-trigger={card.key}
            onClick={(event) => {
              event.stopPropagation();
              onMenu(event.currentTarget.getBoundingClientRect());
            }}
          >
            <MoreHorizontal size={16} />
          </Button>
        </>
      }
    />
  );
}

function PlaceholderCard({ card }: { card: Extract<GalleryCard, { kind: 'generating' | 'queued' }> }) {
  const title = imageTitle(card.qr);
  const meta = imageMeta({ variantIndex: card.variantIndex, formatLabel: card.formatLabel });
  const preview =
    card.kind === 'queued' ? (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Circle size={18} />
        <p className="text-sm">Ожидает генерации</p>
      </div>
    ) : (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Loader2 size={22} className="animate-spin text-primary" />
        <p className="text-sm">Создаём изображение</p>
      </div>
    );

  return (
    <CardShell
      preview={preview}
      title={title}
      meta={meta}
      badgeKey={card.kind === 'generating' ? 'generating' : 'queued'}
    />
  );
}

function CancelledCard({
  card,
  onRetry,
}: {
  card: Extract<GalleryCard, { kind: 'cancelled' }>;
  onRetry?: () => void;
}) {
  const title = imageTitle(card.qr);
  const meta = imageMeta({ variantIndex: card.variantIndex, formatLabel: card.formatLabel });
  return (
    <CardShell
      preview={
        <div className="flex h-full flex-col items-center justify-center gap-2 text-center px-3">
          <p className="text-sm text-muted-foreground">Генерация остановлена</p>
        </div>
      }
      title={title}
      meta={meta}
      badgeKey="cancelled"
      actions={
        onRetry ? (
          <Button size="sm" variant="secondary" className="flex-1" onClick={onRetry}>
            Запустить заново
          </Button>
        ) : undefined
      }
    />
  );
}

function FailedCard({
  card,
  onRetry,
}: {
  card: Extract<GalleryCard, { kind: 'failed' }>;
  onRetry: () => void;
}) {
  const title = imageTitle(card.qr);
  const meta = imageMeta({ variantIndex: card.variantIndex, formatLabel: card.formatLabel });
  return (
    <CardShell
      preview={
        <div className="flex h-full flex-col items-center justify-center gap-2 text-center px-3">
          <AlertCircle size={20} className="text-destructive" />
          <p className="text-sm text-destructive">Не удалось создать изображение</p>
        </div>
      }
      title={title}
      meta={meta}
      badgeKey="failed"
      actions={
        <Button size="sm" variant="secondary" className="flex-1" onClick={onRetry}>
          Повторить
        </Button>
      }
    />
  );
}

function ImageOverflowMenu({
  card,
  rect,
  busy,
  onClose,
  onOpen,
  onDownload,
  onRegenerate,
  onUnpublish,
  onDelete,
}: {
  card: Extract<GalleryCard, { kind: 'ready' }>;
  rect: DOMRect;
  busy: boolean;
  onClose: () => void;
  onOpen: () => void;
  onDownload: () => void;
  onRegenerate: () => void;
  onUnpublish: () => void;
  onDelete: () => void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const width = 208;
  const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
  const [top, setTop] = useState(rect.bottom + 4);
  const published = card.item.status === 'active';
  const src = creativeImageSrc(card.item);

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
      if (target?.closest(`[data-promo-image-menu-trigger="${card.key}"]`)) return;
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
  }, [card.key, onClose]);

  const run = (action: () => void) => {
    action();
    onClose();
  };

  return createPortal(
    <div
      ref={menuRef}
      role="menu"
      className="fixed z-50 ui-card py-1 w-52 text-sm shadow-soft"
      style={{ top, left }}
    >
      {src && <MenuItem onClick={() => run(onOpen)}>Открыть</MenuItem>}
      {!published && src && <MenuItem onClick={() => run(onDownload)}>Скачать</MenuItem>}
      <MenuItem disabled={busy} onClick={() => run(onRegenerate)}>
        Перегенерировать
      </MenuItem>
      {published && <MenuItem onClick={() => run(onUnpublish)}>Снять с публикации</MenuItem>}
      <MenuItem destructive onClick={() => run(onDelete)}>
        Удалить
      </MenuItem>
    </div>,
    document.body,
  );
}

function MenuItem({
  children,
  onClick,
  destructive = false,
  disabled = false,
}: {
  children: string;
  onClick: () => void;
  destructive?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      className={cn(
        'w-full text-left px-3 py-1.5 hover:bg-muted disabled:opacity-50 disabled:pointer-events-none',
        destructive ? 'text-destructive' : 'text-foreground',
      )}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function PromoImageLightbox({
  item,
  variantIndex,
  busy,
  publishPending,
  onClose,
  onDownload,
  onRegenerate,
  onPublish,
  onUnpublish,
}: {
  item: Creative;
  variantIndex: number;
  busy: boolean;
  publishPending?: boolean;
  onClose: () => void;
  onDownload: () => void;
  onRegenerate: () => void;
  onPublish: () => void;
  onUnpublish: () => void;
}) {
  const qr = item.selected_variant === 'images_qr';
  const formatLabel = FORMAT_LABELS[item.format || ''] || item.format || '1:1';
  const src = creativeImageSrc(item);
  const badge = STATUS_LABELS[item.status] || STATUS_LABELS.draft;
  const title = imageTitle(qr);
  const meta = imageMeta({
    variantIndex,
    formatLabel,
    width: item.asset?.width,
    height: item.asset?.height,
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/40" onClick={onClose} />
      <div
        className="relative ui-card w-full max-w-3xl max-h-[92vh] flex flex-col shadow-soft"
        role="dialog"
        aria-modal="true"
        aria-labelledby="promo-image-lightbox-title"
      >
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border/70">
          <div className="min-w-0">
            <h2 id="promo-image-lightbox-title" className="ui-section-title">
              {title}
            </h2>
            <p className="text-xs text-muted-foreground mt-1">{meta}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={cn('ui-badge', badge.className)}>{badge.label}</span>
            <button
              type="button"
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground"
              aria-label="Закрыть"
            >
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-4 bg-muted/30">
          {src ? (
            <img
              src={src}
              alt={`${title}, ${meta}`}
              className="mx-auto max-h-[min(70vh,720px)] w-auto max-w-full object-contain"
            />
          ) : (
            <p className="text-sm text-muted-foreground text-center py-16">Изображение ещё не готово.</p>
          )}
        </div>
        <div className="px-5 py-4 border-t border-border/70 flex flex-wrap justify-end gap-2">
          {src && (
            <Button size="sm" variant="secondary" onClick={onDownload}>
              Скачать
            </Button>
          )}
          <Button size="sm" variant="secondary" disabled={busy} onClick={onRegenerate}>
            Перегенерировать
          </Button>
          {item.status === 'draft' ? (
            <Button size="sm" disabled={publishPending || busy} onClick={onPublish}>
              Опубликовать
            </Button>
          ) : item.status === 'active' ? (
            <Button size="sm" variant="secondary" onClick={onUnpublish}>
              Снять с публикации
            </Button>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}

function buildGalleryCards(images: Creative[], run: PromoGenerationRun | null): GalleryCard[] {
  const byId = new Map(images.map((item) => [item.id, item]));
  const claimed = new Set<number>();
  const cards: GalleryCard[] = [];
  const runItems = (run?.items || [])
    .filter((item) => item.group === 'image')
    .sort((a, b) => a.id - b.id);

  for (const gen of runItems) {
    const meta = slotMeta(gen.material_type);
    const ids = materialIds(gen);
    const expected = Math.max(meta.count, ids.length || 0, 1);

    if (gen.status === 'failed') {
      ids.forEach((id, index) => {
        const item = byId.get(id);
        if (!item) return;
        claimed.add(id);
        cards.push(readyCard(`slot-${gen.id}-${index}`, item, index + 1, meta));
      });
      cards.push({
        kind: 'failed',
        key: `slot-${gen.id}-failed`,
        variantIndex: ids.length + 1,
        formatLabel: meta.formatLabel,
        qr: meta.qr,
        generationItem: gen,
      });
      continue;
    }

    if (gen.status === 'cancelled') {
      if (ids.length) {
        ids.forEach((id, index) => {
          const item = byId.get(id);
          if (!item) return;
          claimed.add(id);
          cards.push(readyCard(`slot-${gen.id}-${index}`, item, index + 1, meta));
        });
      } else {
        for (let index = 0; index < expected; index += 1) {
          cards.push({
            kind: 'cancelled',
            key: `slot-${gen.id}-${index}`,
            variantIndex: index + 1,
            formatLabel: meta.formatLabel,
            qr: meta.qr,
            generationItem: index === 0 ? gen : undefined,
          });
        }
      }
      continue;
    }

    if (gen.status === 'queued') {
      for (let index = 0; index < expected; index += 1) {
        cards.push({
          kind: 'queued',
          key: `slot-${gen.id}-${index}`,
          variantIndex: index + 1,
          formatLabel: meta.formatLabel,
          qr: meta.qr,
        });
      }
      continue;
    }

    const readyItems = ids.map((id) => byId.get(id)).filter((item): item is Creative => !!item);
    readyItems.forEach((item, index) => {
      claimed.add(item.id);
      cards.push(readyCard(`slot-${gen.id}-${index}`, item, index + 1, meta));
    });
    const remaining = Math.max(0, expected - readyItems.length);
    for (let index = 0; index < remaining; index += 1) {
      cards.push({
        kind: 'generating',
        key: `slot-${gen.id}-${readyItems.length + index}`,
        variantIndex: readyItems.length + index + 1,
        formatLabel: meta.formatLabel,
        qr: meta.qr,
      });
    }
  }

  const rest = images.filter((item) => !claimed.has(item.id)).sort((a, b) => b.id - a.id);
  const variantBySlot = new Map<string, number>();
  rest.forEach((item) => {
    const slot = item.selected_variant || item.format || 'asset';
    const variantIndex = (variantBySlot.get(slot) || 0) + 1;
    variantBySlot.set(slot, variantIndex);
    const qr = item.selected_variant === 'images_qr';
    const formatLabel = FORMAT_LABELS[item.format || ''] || '1:1';
    cards.push({
      kind: 'ready',
      key: `asset-${item.id}`,
      item,
      variantIndex,
      formatLabel,
      qr,
    });
  });

  return cards;
}

function readyCard(
  key: string,
  item: Creative,
  variantIndex: number,
  meta: { formatLabel: string; qr: boolean },
): Extract<GalleryCard, { kind: 'ready' }> {
  return {
    kind: 'ready',
    key,
    item,
    variantIndex,
    formatLabel: FORMAT_LABELS[item.format || ''] || meta.formatLabel,
    qr: meta.qr || item.selected_variant === 'images_qr',
  };
}

function materialIds(item: PromoGenerationItem) {
  if (item.material_ids?.length) return item.material_ids;
  if (item.promo_material_id) return [item.promo_material_id];
  return [];
}

function slotMeta(slotId: string) {
  return (
    IMAGE_SLOT_META[slotId] || {
      formatLabel: inferFormatLabel(slotId),
      count: 1,
      qr: slotId === 'images_qr',
    }
  );
}

function inferFormatLabel(slotId: string) {
  if (slotId.includes('16_9')) return '16:9';
  if (slotId.includes('9_16')) return '9:16';
  if (slotId.includes('4_5')) return '4:5';
  return '1:1';
}

function availableFilters(cards: GalleryCard[]): { id: ImageFilter; label: string }[] {
  const counts: Record<ImageFilter, number> = { all: cards.length, '1:1': 0, '4:5': 0, '16:9': 0, '9:16': 0, qr: 0 };
  for (const card of cards) {
    if (card.qr) counts.qr += 1;
    else if (card.formatLabel === '1:1') counts['1:1'] += 1;
    else if (card.formatLabel === '4:5') counts['4:5'] += 1;
    else if (card.formatLabel === '16:9') counts['16:9'] += 1;
    else if (card.formatLabel === '9:16') counts['9:16'] += 1;
  }
  const present = (['1:1', '4:5', '16:9', '9:16', 'qr'] as ImageFilter[]).filter((id) => counts[id] > 0);
  if (present.length <= 1) return [];
  return [
    { id: 'all' as const, label: `Все ${counts.all}` },
    ...present.map((id) => ({ id, label: `${id === 'qr' ? 'С QR' : id} ${counts[id]}` })),
  ];
}

function matchesFilter(card: GalleryCard, filter: ImageFilter) {
  if (filter === 'all') return true;
  if (filter === 'qr') return card.qr;
  return !card.qr && card.formatLabel === filter;
}

function imageTitle(qr: boolean) {
  return qr ? 'Изображение с QR' : 'Промо-изображение';
}

function imageMeta({
  variantIndex,
  formatLabel,
  width,
  height,
}: {
  variantIndex: number;
  formatLabel: string;
  width?: number;
  height?: number;
}) {
  const parts = [`Вариант ${variantIndex}`, formatLabel];
  if (width && height) parts.push(`${width}×${height}`);
  return parts.join(' · ');
}

function creativeImageSrc(item: Creative) {
  if (!item.asset?.url) return '';
  return `${item.asset.url}${item.updated_at ? `?t=${encodeURIComponent(item.updated_at)}` : ''}`;
}

function variantIndexFor(item: Creative, images: Creative[]) {
  const slot = item.selected_variant || '';
  const group = images
    .filter((entry) => (slot ? entry.selected_variant === slot : entry.format === item.format))
    .sort((a, b) => a.id - b.id);
  const index = group.findIndex((entry) => entry.id === item.id);
  return index >= 0 ? index + 1 : 1;
}
