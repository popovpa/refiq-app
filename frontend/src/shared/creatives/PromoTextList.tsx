import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Copy, Loader2, MoreHorizontal, X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import {
  STATUS_LABELS,
  TEXT_CHANNEL_LABELS,
  formatSingleVariant,
  ruCount,
} from './labels';
import type { Creative, CreativeTextVariant, PromoGenerationItem, PromoGenerationRun } from './types';

const SLOT_ORDER = [
  'telegram',
  'meta_ads',
  'google_ads',
  'yandex_direct',
  'vk_ads',
  'tiktok_ads',
  'telegram_posts',
  'vk_posts',
  'universal_ad',
  'short_ad',
  'headlines',
  'descriptions',
];

const LIST_PREVIEW = 3;
const YANDEX_HEADLINE_PREVIEW = 2;
const YANDEX_DESC_PREVIEW = 1;
const TECH_ERROR = /traceback|exception|stack|sqlalchemy|asyncpg|postgres|openai|httpx|typeerror|dbapi/i;

type TextLayout = 'yandex' | 'headlines' | 'descriptions' | 'long';

type TextCard =
  | { kind: 'ready'; key: string; slot: string; item: Creative }
  | {
      kind: 'generating' | 'queued';
      key: string;
      slot: string;
      label: string;
      channel: string | null;
    }
  | {
      kind: 'cancelled';
      key: string;
      slot: string;
      label: string;
      channel: string | null;
      generationItem: PromoGenerationItem;
    }
  | {
      kind: 'failed';
      key: string;
      slot: string;
      label: string;
      channel: string | null;
      generationItem: PromoGenerationItem;
    };

export type TextEditDraft = { headline: string; body: string; cta: string };

interface Props {
  texts: Creative[];
  run: PromoGenerationRun | null;
  showRunPlaceholders: boolean;
  busyId: number | null;
  publishPending?: boolean;
  savePending?: boolean;
  onCopy: (text: string) => void;
  onPublish: (item: Creative) => void;
  onUnpublish: (item: Creative) => void;
  onRegenerate: (item: Creative) => void;
  onDelete: (item: Creative) => void;
  onRetry: (item: PromoGenerationItem) => void;
  onSave: (item: Creative, draft: TextEditDraft) => Promise<void> | void;
}

export function PromoTextList({
  texts,
  run,
  showRunPlaceholders,
  busyId,
  publishPending,
  savePending,
  onCopy,
  onPublish,
  onUnpublish,
  onRegenerate,
  onDelete,
  onRetry,
  onSave,
}: Props) {
  const [activeVariant, setActiveVariant] = useState<Record<number, number>>({});
  const [drawer, setDrawer] = useState<{ item: Creative; editing: boolean } | null>(null);
  const [menu, setMenu] = useState<{ item: Creative; rect: DOMRect } | null>(null);

  const cards = useMemo(
    () => buildTextCards(texts, showRunPlaceholders ? run : null),
    [texts, run, showRunPlaceholders],
  );

  useEffect(() => {
    if (!drawer) return;
    const next = texts.find((item) => item.id === drawer.item.id);
    if (!next) {
      setDrawer(null);
      return;
    }
    if (
      next.status !== drawer.item.status ||
      next.updated_at !== drawer.item.updated_at ||
      next.body !== drawer.item.body ||
      next.headline !== drawer.item.headline
    ) {
      setDrawer((current) => (current ? { ...current, item: next } : current));
    }
  }, [texts, drawer]);

  if (!cards.length) {
    return <p className="text-sm text-muted-foreground">Текстов пока нет.</p>;
  }

  const variantIndex = (item: Creative) => activeVariant[item.id] || 0;

  return (
    <div className="space-y-3">
      {cards.map((card) => {
        if (card.kind === 'ready') {
          return (
            <ReadyTextCard
              key={card.key}
              item={card.item}
              variantIndex={variantIndex(card.item)}
              busy={busyId === card.item.id}
              publishPending={publishPending}
              menuOpen={menu?.item.id === card.item.id}
              onOpen={() => setDrawer({ item: card.item, editing: false })}
              onCopy={() => onCopy(copyPayload(card.item, variantIndex(card.item)))}
              onEdit={() => setDrawer({ item: card.item, editing: true })}
              onPublish={() => onPublish(card.item)}
              onMenu={(rect) =>
                setMenu((current) => (current?.item.id === card.item.id ? null : { item: card.item, rect }))
              }
            />
          );
        }
        if (card.kind === 'failed') {
          return <FailedTextCard key={card.key} card={card} onRetry={() => onRetry(card.generationItem)} />;
        }
        if (card.kind === 'cancelled') {
          return <CancelledTextCard key={card.key} card={card} onRetry={() => onRetry(card.generationItem)} />;
        }
        return <PlaceholderTextCard key={card.key} card={card} />;
      })}

      {menu && (
        <TextOverflowMenu
          item={menu.item}
          rect={menu.rect}
          busy={busyId === menu.item.id}
          onClose={() => setMenu(null)}
          onRegenerate={() => onRegenerate(menu.item)}
          onUnpublish={() => onUnpublish(menu.item)}
          onDelete={() => onDelete(menu.item)}
        />
      )}

      {drawer && (
        <TextDetailDrawer
          item={drawer.item}
          editing={drawer.editing}
          variantIndex={variantIndex(drawer.item)}
          busy={busyId === drawer.item.id}
          publishPending={publishPending}
          savePending={savePending}
          onClose={() => setDrawer(null)}
          onVariant={(index) => setActiveVariant((prev) => ({ ...prev, [drawer.item.id]: index }))}
          onCopy={(text) => onCopy(text)}
          onEdit={() => setDrawer({ item: drawer.item, editing: true })}
          onCancelEdit={() => setDrawer({ item: drawer.item, editing: false })}
          onSave={async (draft) => {
            await onSave(drawer.item, draft);
            setDrawer((current) => (current ? { ...current, editing: false } : current));
          }}
          onPublish={() => onPublish(drawer.item)}
          onUnpublish={() => onUnpublish(drawer.item)}
          onRegenerate={() => onRegenerate(drawer.item)}
          onDelete={() => {
            onDelete(drawer.item);
            setDrawer(null);
          }}
        />
      )}
    </div>
  );
}

function ReadyTextCard({
  item,
  variantIndex,
  busy,
  publishPending,
  menuOpen,
  onOpen,
  onCopy,
  onEdit,
  onPublish,
  onMenu,
}: {
  item: Creative;
  variantIndex: number;
  busy: boolean;
  publishPending?: boolean;
  menuOpen: boolean;
  onOpen: () => void;
  onCopy: () => void;
  onEdit: () => void;
  onPublish: () => void;
  onMenu: (rect: DOMRect) => void;
}) {
  const layout = textLayout(item);
  const title = materialTitle(item);
  const meta = materialMeta(item, layout);
  const badge = STATUS_LABELS[item.status] || STATUS_LABELS.draft;
  const expandLabel = layout === 'long' ? 'Показать полностью' : 'Показать все';
  const previewRef = useRef<HTMLDivElement>(null);
  const [clamped, setClamped] = useState(false);
  const showExpand = needsExpand(item, layout) || clamped;

  useLayoutEffect(() => {
    if (layout !== 'long') {
      setClamped(false);
      return;
    }
    const root = previewRef.current;
    if (!root) return;

    const update = () => {
      const nodes = root.querySelectorAll<HTMLElement>('[data-clamp]');
      if (!nodes.length) {
        setClamped(false);
        return;
      }
      setClamped([...nodes].some(isCssClamped));
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(root);
    return () => observer.disconnect();
  }, [item, variantIndex, layout]);

  return (
    <article className="ui-card px-4 py-3 space-y-1.5 transition-shadow hover:shadow-soft hover:border-border">
      <CardHeader title={title} meta={meta} badge={badge} />

      <div className="relative min-w-0" ref={previewRef}>
        <TextPreview item={item} layout={layout} variantIndex={variantIndex} />
        {busy && (
          <div className="absolute inset-0 flex items-center gap-2 rounded-md bg-card/80 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin text-primary" />
            Обновляем текст…
          </div>
        )}
        {showExpand && (
          <button
            type="button"
            className="mt-1.5 text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 rounded-sm"
            onClick={onOpen}
            aria-label={`${expandLabel}: ${title}`}
          >
            {expandLabel}
          </button>
        )}
      </div>

      {item.policy_status === 'blocked' && (
        <p className="text-xs text-destructive">Нельзя опубликовать: нарушены правила продвижения.</p>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="sm" variant="secondary" onClick={onCopy} aria-label={`Скопировать: ${title}`}>
          <Copy size={14} />
          Скопировать
        </Button>
        <Button size="sm" variant="secondary" onClick={onEdit} disabled={busy}>
          Редактировать
        </Button>
        {item.status === 'draft' && (
          <Button size="sm" disabled={publishPending || busy || item.policy_status === 'blocked'} onClick={onPublish}>
            Опубликовать
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="px-2 ml-auto"
          aria-label="Ещё действия"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          data-promo-text-menu-trigger={item.id}
          onClick={(event) => onMenu(event.currentTarget.getBoundingClientRect())}
        >
          <MoreHorizontal size={16} />
        </Button>
      </div>
    </article>
  );
}

function CardHeader({
  title,
  meta,
  badge,
}: {
  title: string;
  meta?: string;
  badge: { label: string; className: string };
}) {
  return (
    <header className="flex items-start justify-between gap-3 min-h-0">
      <div className="min-w-0 flex flex-col">
        <p className="text-sm font-medium leading-5 truncate">{title}</p>
        {meta ? <p className="text-xs leading-4 text-muted-foreground">{meta}</p> : null}
      </div>
      <span className={cn('ui-badge shrink-0', badge.className)}>{badge.label}</span>
    </header>
  );
}

function PlaceholderTextCard({
  card,
}: {
  card: Extract<TextCard, { kind: 'generating' | 'queued' }>;
}) {
  const title = card.label || 'Текст';
  const channel = channelLabel(card.channel);
  const badgeKey = card.kind === 'generating' ? 'generating' : 'queued';
  const badge = STATUS_LABELS[badgeKey];
  const preview = card.kind === 'queued' ? 'Материал в очереди' : 'Создаём варианты текста…';

  return (
    <article className="ui-card px-4 py-3 space-y-1.5" aria-busy>
      <CardHeader title={title} meta={channel} badge={badge} />
      <p className="flex items-center gap-2 text-sm leading-5 text-muted-foreground">
        <Loader2 size={16} className="animate-spin text-primary shrink-0" />
        {preview}
      </p>
    </article>
  );
}

function CancelledTextCard({
  card,
  onRetry,
}: {
  card: Extract<TextCard, { kind: 'cancelled' }>;
  onRetry: () => void;
}) {
  const title = card.label || 'Текст';
  const channel = channelLabel(card.channel);
  const badge = STATUS_LABELS.cancelled;

  return (
    <article className="ui-card px-4 py-3 space-y-1.5">
      <CardHeader title={title} meta={channel} badge={badge} />
      <p className="text-sm leading-5 text-muted-foreground">Генерация материала остановлена</p>
      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Запустить заново
        </Button>
      </div>
    </article>
  );
}

function FailedTextCard({
  card,
  onRetry,
}: {
  card: Extract<TextCard, { kind: 'failed' }>;
  onRetry: () => void;
}) {
  const title = card.label || 'Текст';
  const channel = channelLabel(card.channel);
  const badge = STATUS_LABELS.failed;
  const detail = safeError(card.generationItem);

  return (
    <article className="ui-card px-4 py-3 space-y-1.5">
      <CardHeader title={title} meta={channel} badge={badge} />
      <p className="text-sm leading-5 text-destructive">Не удалось создать материал</p>
      {detail && <p className="text-xs leading-4 text-muted-foreground">{detail}</p>}
      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Повторить
        </Button>
      </div>
    </article>
  );
}

function TextPreview({
  item,
  layout,
  variantIndex,
}: {
  item: Creative;
  layout: TextLayout;
  variantIndex: number;
}) {
  if (layout === 'yandex') {
    const headlines = item.items?.filter(Boolean) || [];
    const descriptions = item.descriptions?.filter(Boolean) || [];
    return (
      <div className="space-y-1">
        <PreviewList title="Заголовки" items={headlines} limit={YANDEX_HEADLINE_PREVIEW} />
        <PreviewList title="Описания" items={descriptions} limit={YANDEX_DESC_PREVIEW} />
      </div>
    );
  }
  if (layout === 'headlines' || layout === 'descriptions') {
    return <PreviewList items={listLines(item)} limit={LIST_PREVIEW} />;
  }
  return <LongPreview variant={longVariants(item)[variantIndex] || longVariants(item)[0] || item} />;
}

function PreviewList({ title, items, limit }: { title?: string; items: string[]; limit: number }) {
  const visible = items.slice(0, limit);
  const hidden = Math.max(0, items.length - visible.length);
  return (
    <div>
      {title && <p className="text-xs font-medium text-foreground leading-4">{title}</p>}
      <ol>
        {visible.map((line, index) => (
          <li key={`${index}-${line.slice(0, 24)}`} className="flex gap-1 text-sm leading-5 min-w-0">
            <span className="text-foreground/70 tabular-nums shrink-0">{index + 1}.</span>
            <span className="text-muted-foreground line-clamp-1 break-words min-w-0">{line}</span>
          </li>
        ))}
      </ol>
      {hidden > 0 && <p className="text-xs leading-4 text-muted-foreground">+{hidden}</p>}
    </div>
  );
}

function LongPreview({ variant }: { variant: CreativeTextVariant }) {
  const headline = previewLine(variant.headline);
  const body = previewLine([variant.body, variant.cta].filter(Boolean).join(' '));
  if (!headline && !body) {
    return (
      <p data-text-preview data-clamp className="text-sm text-muted-foreground leading-5">
        Текст ещё не заполнен.
      </p>
    );
  }
  return (
    <div data-text-preview className="min-w-0 space-y-0.5">
      {headline ? (
        <p data-clamp className="text-sm font-medium leading-5 line-clamp-1 break-words">
          {headline}
        </p>
      ) : null}
      {body ? (
        <p
          data-clamp
          className={cn(
            'text-sm text-muted-foreground break-words leading-5',
            headline ? 'line-clamp-2' : 'line-clamp-3',
          )}
        >
          {body}
        </p>
      ) : null}
    </div>
  );
}

function TextDetailDrawer({
  item,
  editing,
  variantIndex,
  busy,
  publishPending,
  savePending,
  onClose,
  onVariant,
  onCopy,
  onEdit,
  onCancelEdit,
  onSave,
  onPublish,
  onUnpublish,
  onRegenerate,
  onDelete,
}: {
  item: Creative;
  editing: boolean;
  variantIndex: number;
  busy: boolean;
  publishPending?: boolean;
  savePending?: boolean;
  onClose: () => void;
  onVariant: (index: number) => void;
  onCopy: (text: string) => void;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSave: (draft: TextEditDraft) => void | Promise<void>;
  onPublish: () => void;
  onUnpublish: () => void;
  onRegenerate: () => void;
  onDelete: () => void;
}) {
  const layout = textLayout(item);
  const title = materialTitle(item);
  const badge = STATUS_LABELS[item.status] || STATUS_LABELS.draft;
  const variants = longVariants(item);
  const safeIndex = Math.min(variantIndex, Math.max(0, variants.length - 1));
  const [menu, setMenu] = useState<DOMRect | null>(null);
  const [draft, setDraft] = useState<TextEditDraft>({
    headline: item.headline || '',
    body: item.body || '',
    cta: item.cta || '',
  });

  useEffect(() => {
    if (editing) {
      setDraft({ headline: item.headline || '', body: item.body || '', cta: item.cta || '' });
    }
  }, [editing, item.id, item.updated_at, item.headline, item.body, item.cta]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const channel = channelLabel(item.channel);
  const metaParts = [channel && channel !== title ? channel : null, badge.label, variantSummary(item, layout)].filter(
    Boolean,
  );

  return (
    <div className="fixed inset-0 z-[60] flex justify-end">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <aside
        className="relative ui-card w-full max-w-xl h-full shadow-soft flex flex-col border-l"
        role="dialog"
        aria-modal="true"
        aria-labelledby="promo-text-drawer-title"
      >
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border/70">
          <div className="min-w-0">
            <h2 id="promo-text-drawer-title" className="ui-section-title">
              {title}
            </h2>
            <p className="text-xs text-muted-foreground mt-1">{metaParts.join(' · ')}</p>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5 space-y-4">
          {editing ? (
            <div className="space-y-2">
              <input
                className="ui-input"
                value={draft.headline}
                onChange={(event) => setDraft({ ...draft, headline: event.target.value })}
                placeholder="Заголовок"
                aria-label="Заголовок"
              />
              <textarea
                className="ui-input min-h-[160px] h-auto py-2"
                value={draft.body}
                onChange={(event) => setDraft({ ...draft, body: event.target.value })}
                placeholder="Текст"
                aria-label="Текст"
              />
              <input
                className="ui-input"
                value={draft.cta}
                onChange={(event) => setDraft({ ...draft, cta: event.target.value })}
                placeholder="CTA"
                aria-label="Призыв к действию"
              />
            </div>
          ) : layout === 'yandex' ? (
            <YandexDetail
              headlines={item.items?.filter(Boolean) || []}
              descriptions={item.descriptions?.filter(Boolean) || []}
              onCopy={onCopy}
            />
          ) : layout === 'headlines' || layout === 'descriptions' ? (
            <ListDetail items={listLines(item)} />
          ) : (
            <>
              {variants.length > 1 && (
                <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Варианты текста">
                  {variants.map((_, index) => (
                    <button
                      key={index}
                      type="button"
                      role="tab"
                      aria-selected={safeIndex === index}
                      className={cn(
                        'h-7 px-2.5 rounded-full text-xs font-medium border transition-colors',
                        safeIndex === index
                          ? 'border-primary/30 bg-accent text-primary'
                          : 'border-border/80 bg-card text-muted-foreground hover:text-foreground',
                      )}
                      onClick={() => onVariant(index)}
                    >
                      Вариант {index + 1}
                    </button>
                  ))}
                </div>
              )}
              <p className="text-sm whitespace-pre-wrap break-words leading-6">
                {formatSingleVariant(variants[safeIndex] || item) || 'Текст ещё не заполнен.'}
              </p>
            </>
          )}
          {item.policy_status === 'blocked' && (
            <p className="text-xs text-destructive">Нельзя опубликовать: нарушены правила продвижения.</p>
          )}
        </div>

        <div className="px-5 py-4 border-t border-border/70 flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button
                size="sm"
                disabled={savePending}
                onClick={() => {
                  void Promise.resolve(onSave(draft)).catch(() => undefined);
                }}
              >
                Сохранить
              </Button>
              <Button size="sm" variant="ghost" onClick={onCancelEdit}>
                Отмена
              </Button>
            </>
          ) : (
            <>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => onCopy(copyPayload(item, safeIndex))}
                aria-label={`Скопировать: ${title}`}
              >
                <Copy size={14} />
                Скопировать
              </Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={onEdit}>
                Редактировать
              </Button>
              {item.status === 'draft' && (
                <Button
                  size="sm"
                  disabled={publishPending || busy || item.policy_status === 'blocked'}
                  onClick={onPublish}
                >
                  Опубликовать
                </Button>
              )}
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="px-2 ml-auto"
                aria-label="Ещё действия"
                aria-haspopup="menu"
                aria-expanded={!!menu}
                data-promo-text-menu-trigger={`drawer-${item.id}`}
                onClick={(event) => setMenu(event.currentTarget.getBoundingClientRect())}
              >
                <MoreHorizontal size={16} />
              </Button>
            </>
          )}
        </div>
      </aside>
      {menu && (
        <TextOverflowMenu
          item={item}
          rect={menu}
          busy={busy}
          triggerId={`drawer-${item.id}`}
          onClose={() => setMenu(null)}
          onRegenerate={onRegenerate}
          onUnpublish={onUnpublish}
          onDelete={onDelete}
        />
      )}
    </div>
  );
}

function YandexDetail({
  headlines,
  descriptions,
  onCopy,
}: {
  headlines: string[];
  descriptions: string[];
  onCopy: (text: string) => void;
}) {
  return (
    <div className="space-y-5">
      <CopyableList title="Заголовки" items={headlines} onCopy={onCopy} />
      <CopyableList title="Описания" items={descriptions} onCopy={onCopy} />
    </div>
  );
}

function CopyableList({ title, items, onCopy }: { title: string; items: string[]; onCopy: (text: string) => void }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        {!!items.length && (
          <Button size="sm" variant="ghost" onClick={() => onCopy(numbered(items))} aria-label={`Скопировать: ${title}`}>
            <Copy size={14} />
            Скопировать
          </Button>
        )}
      </div>
      <ListDetail items={items} />
    </section>
  );
}

function ListDetail({ items }: { items: string[] }) {
  if (!items.length) {
    return <p className="text-sm text-muted-foreground">Список пуст.</p>;
  }
  return (
    <ol className="space-y-2">
      {items.map((line, index) => (
        <li key={`${index}-${line.slice(0, 32)}`} className="text-sm leading-6">
          <span className="text-muted-foreground tabular-nums">{index + 1}. </span>
          {line}
        </li>
      ))}
    </ol>
  );
}

function TextOverflowMenu({
  item,
  rect,
  busy,
  triggerId,
  onClose,
  onRegenerate,
  onUnpublish,
  onDelete,
}: {
  item: Creative;
  rect: DOMRect;
  busy: boolean;
  triggerId?: string;
  onClose: () => void;
  onRegenerate: () => void;
  onUnpublish: () => void;
  onDelete: () => void;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const width = 220;
  const left = Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8));
  const [top, setTop] = useState(rect.bottom + 4);
  const published = item.status === 'active';
  const trigger = triggerId || String(item.id);

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
      if (target?.closest(`[data-promo-text-menu-trigger="${trigger}"]`)) return;
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
  }, [onClose, trigger]);

  const run = (action: () => void) => {
    action();
    onClose();
  };

  return createPortal(
    <div ref={menuRef} role="menu" className="fixed z-[70] ui-card py-1 w-52 text-sm shadow-soft" style={{ top, left }}>
      <MenuItem disabled={busy} onClick={() => run(onRegenerate)}>
        Перегенерировать с AI
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

function buildTextCards(texts: Creative[], run: PromoGenerationRun | null): TextCard[] {
  const byId = new Map(texts.map((item) => [item.id, item]));
  const claimed = new Set<number>();
  const cards: TextCard[] = [];
  const runItems = (run?.items || [])
    .filter((item) => item.group === 'text')
    .sort((a, b) => a.id - b.id);

  for (const gen of runItems) {
    const ids = materialIds(gen);
    const readyItems = ids.map((id) => byId.get(id)).filter((item): item is Creative => !!item);
    readyItems.forEach((item) => claimed.add(item.id));

    if (readyItems.length) {
      readyItems.forEach((item, index) => {
        cards.push({
          kind: 'ready',
          key: `slot-${gen.id}-${index}`,
          slot: gen.material_type,
          item,
        });
      });
      continue;
    }

    if (gen.status === 'failed') {
      cards.push({
        kind: 'failed',
        key: `slot-${gen.id}`,
        slot: gen.material_type,
        label: gen.label,
        channel: gen.channel,
        generationItem: gen,
      });
      continue;
    }
    if (gen.status === 'cancelled') {
      cards.push({
        kind: 'cancelled',
        key: `slot-${gen.id}`,
        slot: gen.material_type,
        label: gen.label,
        channel: gen.channel,
        generationItem: gen,
      });
      continue;
    }
    cards.push({
      kind: gen.status === 'queued' ? 'queued' : 'generating',
      key: `slot-${gen.id}`,
      slot: gen.material_type,
      label: gen.label,
      channel: gen.channel,
    });
  }

  const rest = texts.filter((item) => !claimed.has(item.id)).sort(compareTexts);
  rest.forEach((item) => {
    cards.push({
      kind: 'ready',
      key: `asset-${item.id}`,
      slot: item.selected_variant || '',
      item,
    });
  });

  return cards.sort((a, b) => slotIndex(a.slot) - slotIndex(b.slot) || keyFallback(a) - keyFallback(b));
}

function compareTexts(a: Creative, b: Creative) {
  const order = slotIndex(a.selected_variant || '') - slotIndex(b.selected_variant || '');
  return order || a.id - b.id;
}

function slotIndex(slot: string) {
  const index = SLOT_ORDER.indexOf(slot);
  return index === -1 ? SLOT_ORDER.length : index;
}

function keyFallback(card: TextCard) {
  return card.kind === 'ready' ? card.item.id : 0;
}

function materialIds(item: PromoGenerationItem) {
  if (item.material_ids?.length) return item.material_ids;
  if (item.promo_material_id) return [item.promo_material_id];
  return [];
}

function textLayout(item: Creative): TextLayout {
  if (
    item.channel === 'yandex_direct' ||
    item.channel === 'google_ads' ||
    item.channel === 'meta_ads' ||
    item.channel === 'tiktok_ads' ||
    (item.descriptions && item.descriptions.length)
  ) {
    return 'yandex';
  }
  if (item.selected_variant === 'headlines') return 'headlines';
  if (item.selected_variant === 'descriptions') return 'descriptions';
  return 'long';
}

function longVariants(item: Creative): CreativeTextVariant[] {
  if (item.variants && item.variants.length) return item.variants;
  return [{ headline: item.headline, body: item.body, cta: item.cta, hashtags: item.hashtags || [] }];
}

function listLines(item: Creative) {
  if (item.items && item.items.length) return item.items.filter(Boolean);
  return [item.headline, item.body].filter((value): value is string => !!value);
}

function materialTitle(item: Creative) {
  return item.title || 'Текст';
}

function channelLabel(channel: string | null | undefined) {
  if (!channel) return '';
  return TEXT_CHANNEL_LABELS[channel] || channel;
}

function variantSummary(item: Creative, layout: TextLayout) {
  if (layout === 'yandex') {
    const headlines = item.items?.length || 0;
    const descriptions = item.descriptions?.length || 0;
    return [
      headlines ? ruCount(headlines, 'заголовок', 'заголовка', 'заголовков') : null,
      descriptions ? ruCount(descriptions, 'описание', 'описания', 'описаний') : null,
    ]
      .filter(Boolean)
      .join(' · ');
  }
  if (layout === 'headlines' || layout === 'descriptions') {
    const count = listLines(item).length;
    return count > 1 ? ruCount(count, 'вариант', 'варианта', 'вариантов') : '';
  }
  const count = longVariants(item).length;
  return count > 1 ? ruCount(count, 'вариант', 'варианта', 'вариантов') : '';
}

function materialMeta(item: Creative, layout: TextLayout) {
  const title = materialTitle(item);
  const channel = channelLabel(item.channel);
  const summary = variantSummary(item, layout);
  const parts = [channel && channel !== title ? channel : null, summary].filter(Boolean);
  return parts.join(' · ');
}

function needsExpand(item: Creative, layout: TextLayout) {
  if (layout === 'yandex') {
    return (
      (item.items?.length || 0) > YANDEX_HEADLINE_PREVIEW ||
      (item.descriptions?.length || 0) > YANDEX_DESC_PREVIEW
    );
  }
  if (layout === 'headlines' || layout === 'descriptions') {
    return listLines(item).length > LIST_PREVIEW;
  }
  return longVariants(item).length > 1;
}

function copyPayload(item: Creative, variantIndex: number) {
  const layout = textLayout(item);
  if (layout === 'yandex') {
    const headlines = item.items?.filter(Boolean) || [];
    return headlines[variantIndex] || headlines[0] || formatSingleVariant(item);
  }
  if (layout === 'headlines' || layout === 'descriptions') {
    const lines = listLines(item);
    return lines[variantIndex] || lines[0] || '';
  }
  const variants = longVariants(item);
  return formatSingleVariant(variants[Math.min(variantIndex, variants.length - 1)] || item);
}

function numbered(items: string[]) {
  return items.map((line, index) => `${index + 1}. ${line}`).join('\n');
}

function previewLine(value: string | null | undefined) {
  return (value || '').replace(/\s+/g, ' ').trim();
}

function isCssClamped(node: HTMLElement) {
  const clone = node.cloneNode(true) as HTMLElement;
  clone.className = node.className.replace(/line-clamp-\d+/g, '');
  clone.style.cssText = [
    'position:absolute',
    'visibility:hidden',
    'pointer-events:none',
    'display:block',
    'height:auto',
    'max-height:none',
    'overflow:visible',
    'white-space:normal',
    '-webkit-line-clamp:unset',
    'line-clamp:unset',
    `width:${node.offsetWidth}px`,
  ].join(';');
  node.parentElement?.appendChild(clone);
  const overflowing = clone.scrollHeight > node.clientHeight + 1;
  clone.remove();
  return overflowing;
}

function safeError(item: PromoGenerationItem) {
  const message = (item.error_message || '').trim();
  if (!message || TECH_ERROR.test(message) || message.length > 140) return '';
  return message;
}
