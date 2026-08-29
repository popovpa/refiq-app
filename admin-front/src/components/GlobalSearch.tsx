import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api, qs } from '@/lib/api';
import { hrefForSearchItem, type SearchItem } from '@/lib/navigation';
import { entityTypeLabel } from '@/lib/labels';

export function GlobalSearch() {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const boxRef = useRef<HTMLDivElement>(null);
  const query = useQuery({
    queryKey: ['admin-search', q],
    queryFn: () => api.get<{ query: string; items: SearchItem[] }>(`/search${qs({ q })}`),
    enabled: q.trim().length >= 2,
  });

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (!boxRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const items = query.data?.items || [];

  return (
    <div ref={boxRef} className="relative flex-1 max-w-2xl">
      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && items[0]) {
            navigate(hrefForSearchItem(items[0]));
            setOpen(false);
          }
        }}
        placeholder="Поиск: бизнес, домен, email, rqcid, shortCode…"
        className="ui-input pl-9 h-9"
      />
      {open && q.trim().length >= 2 && (
        <div className="absolute z-40 mt-1 w-full ui-card shadow-soft max-h-96 overflow-auto">
          {query.isLoading && <div className="px-3 py-2 text-sm text-muted-foreground">Поиск…</div>}
          {!query.isLoading && items.length === 0 && (
            <div className="px-3 py-2 text-sm text-muted-foreground">Ничего не найдено</div>
          )}
          {items.map((item) => (
            <button
              type="button"
              key={`${item.type}-${item.id}`}
              className="w-full text-left px-3 py-2 hover:bg-muted/60 border-t border-border/60 first:border-0"
              onClick={() => {
                navigate(hrefForSearchItem(item));
                setOpen(false);
              }}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{item.title}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {item.subtitle || entityTypeLabel(item.type)}
                    {item.context?.offer ? ` · Оффер: ${item.context.offer}` : ''}
                    {item.context?.business ? ` · Бизнес: ${item.context.business}` : ''}
                    {item.context?.partner ? ` · Партнёр: ${item.context.partner}` : ''}
                  </div>
                </div>
                {item.primary_action === 'open_trace' && (
                  <span className="text-[11px] font-medium text-primary shrink-0">Трассировка</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
