import { useEffect, useId, useRef, useState } from 'react';
import { ChevronDown, Sparkles } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { SHOW_OFFER_AI_NEW_BADGE } from '@/shared/ai/ui';
import { cn } from '@/shared/utils/cn';

export type OfferAiSplitItem = {
  id: string;
  label: string;
  ai?: boolean;
  onSelect: () => void;
};

export function OfferAiSplitButton({
  label,
  onPrimary,
  items,
}: {
  label: string;
  onPrimary: () => void;
  items: OfferAiSplitItem[];
}) {
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const chevronRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const close = (restoreFocus = false) => {
    setOpen(false);
    if (restoreFocus) chevronRef.current?.focus();
  };

  const run = (action: () => void) => {
    close();
    action();
  };

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close(true);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    itemRefs.current[activeIndex]?.focus();
  }, [open, activeIndex]);

  const move = (delta: number) => {
    setActiveIndex((current) => (current + delta + items.length) % items.length);
  };

  return (
    <div ref={rootRef} className="relative inline-flex shrink-0">
      <div className="inline-flex rounded-md shadow-sm isolate">
        <Button type="button" className="rounded-r-none shadow-none whitespace-nowrap" onClick={() => run(onPrimary)}>
          <Sparkles size={16} aria-hidden />
          {label}
        </Button>
        <Button
          ref={chevronRef}
          type="button"
          className="rounded-l-none shadow-none px-2.5 border-l border-primary-foreground/25"
          aria-label="Дополнительные действия"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={menuId}
          onClick={() => {
            setActiveIndex(0);
            setOpen((current) => !current);
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              event.preventDefault();
              setActiveIndex(event.key === 'ArrowUp' ? items.length - 1 : 0);
              setOpen(true);
            }
          }}
        >
          <ChevronDown size={16} className={cn('transition-transform', open && 'rotate-180')} aria-hidden />
        </Button>
      </div>

      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 top-full z-30 mt-1 min-w-[15.5rem] ui-card py-1 shadow-soft"
        >
          {items.map((item, index) => (
            <button
              key={item.id}
              ref={(node) => {
                itemRefs.current[index] = node;
              }}
              type="button"
              role="menuitem"
              tabIndex={activeIndex === index ? 0 : -1}
              className="w-full flex items-center justify-between gap-3 px-3 py-1.5 text-sm text-left hover:bg-muted focus-visible:outline-none focus-visible:bg-muted"
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => run(item.onSelect)}
              onKeyDown={(event) => {
                if (event.key === 'ArrowDown') {
                  event.preventDefault();
                  move(1);
                } else if (event.key === 'ArrowUp') {
                  event.preventDefault();
                  move(-1);
                } else if (event.key === 'Home') {
                  event.preventDefault();
                  setActiveIndex(0);
                } else if (event.key === 'End') {
                  event.preventDefault();
                  setActiveIndex(items.length - 1);
                } else if (event.key === 'Tab') {
                  close();
                }
              }}
            >
              <span className="inline-flex items-center gap-2 whitespace-nowrap">
                {item.ai ? <Sparkles size={14} className="text-primary shrink-0" aria-hidden /> : <span className="w-3.5" />}
                {item.label}
              </span>
              {item.ai && SHOW_OFFER_AI_NEW_BADGE && (
                <span className="ui-badge bg-accent text-primary text-[10px] px-1.5 py-0 leading-4">New</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
