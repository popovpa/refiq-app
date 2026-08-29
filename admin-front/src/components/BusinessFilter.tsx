import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Check, ChevronDown, Search } from 'lucide-react';
import { api, qs } from '@/lib/api';
import { cn } from '@/components/ui';
import {
  BUSINESS_FILTER_DEBOUNCE_MS,
  businessFilterTriggerLabel,
  type BusinessLookupItem,
} from '@/lib/businessFilter';

export function BusinessFilter({
  value,
  onChange,
}: {
  value: string;
  onChange: (businessId: string | undefined) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const containerRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), BUSINESS_FILTER_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (open) {
      setSearch('');
      setDebouncedSearch('');
      window.setTimeout(() => searchRef.current?.focus(), 0);
    }
  }, [open]);

  const selectedQuery = useQuery({
    queryKey: ['business-lookup', 'selected', value],
    queryFn: () => api.get<BusinessLookupItem[]>(`/businesses/lookup${qs({ id: value })}`),
    enabled: Boolean(value),
  });

  const listQuery = useQuery({
    queryKey: ['business-lookup', 'list', debouncedSearch],
    queryFn: () => api.get<BusinessLookupItem[]>(`/businesses/lookup${qs({ search: debouncedSearch || undefined })}`),
    enabled: open,
  });

  const selectedName = selectedQuery.data?.find((item) => String(item.id) === value)?.name;
  const items = listQuery.data || [];
  const listPending =
    listQuery.isLoading || listQuery.isFetching || search.trim() !== debouncedSearch;

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Фильтр по бизнесу"
        onClick={() => setOpen((current) => !current)}
        className={cn(
          'ui-input h-8 w-56 flex items-center justify-between gap-2 text-left',
          open && 'ring-2 ring-primary/30 border-primary/40',
        )}
      >
        <span className="truncate">
          <span className="text-muted-foreground">Бизнес: </span>
          {businessFilterTriggerLabel(selectedName, value)}
        </span>
        <ChevronDown size={14} className={cn('text-muted-foreground shrink-0 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 w-72 ui-card shadow-soft p-1">
          <div className="relative px-1 pt-1 pb-1">
            <Search size={14} className="absolute left-3.5 top-[18px] text-muted-foreground pointer-events-none" />
            <input
              ref={searchRef}
              className="ui-input h-8 pl-8"
              placeholder="Поиск бизнеса..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div role="listbox" aria-label="Бизнес" className="max-h-56 overflow-auto py-1">
            <button
              type="button"
              role="option"
              aria-selected={!value}
              className={cn(
                'w-full text-left px-3 py-2 text-sm rounded-md hover:bg-muted/60',
                !value && 'bg-muted/60',
              )}
              onClick={() => {
                onChange(undefined);
                setOpen(false);
              }}
            >
              <span className="flex items-center justify-between gap-2">
                Все бизнесы
                {!value && <Check size={14} className="text-primary shrink-0" />}
              </span>
            </button>
            {listPending && (
              <div className="px-3 py-2 text-sm text-muted-foreground">Загрузка…</div>
            )}
            {listQuery.isError && !listPending && (
              <div className="px-3 py-2 text-sm text-destructive">Не удалось загрузить бизнесы</div>
            )}
            {!listPending && !listQuery.isError && items.length === 0 && (
              <div className="px-3 py-2 text-sm text-muted-foreground">Бизнесы не найдены</div>
            )}
            {!listPending && items.map((item) => {
              const selected = String(item.id) === value;
              return (
                <button
                  key={String(item.id)}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={cn(
                    'w-full text-left px-3 py-2 text-sm rounded-md hover:bg-muted/60',
                    selected && 'bg-muted/60',
                  )}
                  onClick={() => {
                    onChange(String(item.id));
                    setOpen(false);
                  }}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate">{item.name}</span>
                    {selected && <Check size={14} className="text-primary shrink-0" />}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
