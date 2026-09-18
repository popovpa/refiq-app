import { useEffect, useId, useRef, useState } from 'react';
import { LoaderCircle, Search } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import {
  type LegalEntityCandidate,
  type LookupContext,
  registryIdLine,
  shouldSearch,
  subjectTypeShortLabel,
  usedInLabel,
} from '@/shared/finance/lookup';
import { verificationStatusLabel } from '@/shared/finance/legalEntity';

type SearchState = 'idle' | 'searching' | 'results' | 'empty' | 'error';

export function LegalEntityLookup({
  context,
  subjectType,
  onSelect,
  onManual,
  selecting,
}: {
  context: LookupContext;
  subjectType: string;
  onSelect: (candidate: LegalEntityCandidate) => void;
  onManual: () => void;
  selecting?: boolean;
}) {
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  const [state, setState] = useState<SearchState>('idle');
  const [items, setItems] = useState<LegalEntityCandidate[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebounced(query), 300);
    return () => window.clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    if (!shouldSearch(debounced)) {
      setItems([]);
      setState('idle');
      return;
    }
    let cancelled = false;
    setState('searching');
    const params = new URLSearchParams({ query: debounced, context, subject_type: subjectType });
    api
      .get<{ items: LegalEntityCandidate[] }>(`/legal-entity-lookup/search?${params}`)
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setState(data.items.length ? 'results' : 'empty');
        setOpen(true);
        setActiveIndex(data.items.length ? 0 : -1);
      })
      .catch(() => {
        if (cancelled) return;
        setItems([]);
        setState('error');
        setOpen(true);
      });
    return () => {
      cancelled = true;
    };
  }, [debounced, context, subjectType]);

  const choose = (item: LegalEntityCandidate) => {
    setOpen(false);
    onSelect(item);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setOpen(false);
      return;
    }
    if (event.key === 'ArrowDown' && items.length) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => (current + 1) % items.length);
    }
    if (event.key === 'ArrowUp' && items.length) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => (current <= 0 ? items.length - 1 : current - 1));
    }
    if (event.key === 'Enter' && open && activeIndex >= 0 && items[activeIndex]) {
      event.preventDefault();
      choose(items[activeIndex]);
    }
  };

  return (
    <div className="space-y-3">
      <div className="relative">
        <label className="ui-label" htmlFor={`${listId}-input`}>
          Найдите организацию или ИП
        </label>
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <input
            id={`${listId}-input`}
            ref={inputRef}
            className="ui-input pl-9"
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={activeIndex >= 0 ? `${listId}-opt-${activeIndex}` : undefined}
            placeholder="ИНН, ОГРН, название организации или ФИО ИП"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            onKeyDown={onKeyDown}
            onFocus={() => items.length && setOpen(true)}
            disabled={selecting}
          />
          {state === 'searching' && (
            <LoaderCircle size={16} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground" />
          )}
        </div>
        {open && (state === 'results' || state === 'empty' || state === 'error') && (
          <div
            id={listId}
            role="listbox"
            className="absolute z-20 mt-1 w-full max-h-72 overflow-auto ui-card p-1 shadow-soft"
          >
            {state === 'results' &&
              items.map((item, index) => (
                <button
                  key={item.candidate_id}
                  id={`${listId}-opt-${index}`}
                  type="button"
                  role="option"
                  aria-selected={index === activeIndex}
                  className={cn(
                    'w-full text-left rounded-lg px-3 py-2.5 transition-colors',
                    index === activeIndex ? 'bg-accent' : 'hover:bg-muted/60',
                  )}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => choose(item)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-medium truncate">{item.display_name}</p>
                    <span className="ui-badge shrink-0 bg-muted text-muted-foreground">
                      {item.reuse_available && item.verification_status
                        ? verificationStatusLabel(item.verification_status)
                        : subjectTypeShortLabel(item.subject_type)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{registryIdLine(item)}</p>
                  <div className="mt-0.5 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                    <span className="truncate">{item.region || item.address_summary || ' '}</span>
                    <span>{item.reuse_available ? usedInLabel(item.used_in) : 'Действует'}</span>
                  </div>
                </button>
              ))}
            {state === 'empty' && (
              <div className="px-3 py-3 text-sm space-y-2">
                <p className="font-medium">Организация не найдена</p>
                <Button type="button" size="sm" variant="secondary" onClick={onManual}>
                  Заполнить данные вручную
                </Button>
              </div>
            )}
            {state === 'error' && (
              <div className="px-3 py-3 text-sm space-y-2">
                <p className="font-medium">Не удалось выполнить поиск.</p>
                <p className="text-muted-foreground">Попробуйте ещё раз или заполните данные вручную.</p>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="secondary" onClick={() => setDebounced(`${query} `)}>
                    Повторить
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={onManual}>
                    Заполнить вручную
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <button type="button" className="text-sm text-muted-foreground hover:text-foreground" onClick={onManual}>
        Не нашли организацию? Заполнить вручную
      </button>
    </div>
  );
}
