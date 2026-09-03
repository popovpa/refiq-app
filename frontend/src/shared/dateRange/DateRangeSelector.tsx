import { useEffect, useMemo, useRef, useState } from 'react';
import { CalendarDays, ChevronDown } from 'lucide-react';
import { cn } from '@/shared/utils/cn';
import { useDateRange } from './useDateRange';
import {
  CUSTOM_RANGE_LABEL,
  DATE_RANGE_PRESET_LABELS,
  DATE_RANGE_PRESETS,
  type DateRangePreset,
} from './types';
import { calendarDateFromInstant, toIsoDate } from './timezone';

function formatCustomLabel(state: { dateFrom: Date; dateTo: Date; timezone: string }): string {
  const from = calendarDateFromInstant(state.dateFrom, state.timezone);
  const to = calendarDateFromInstant(state.dateTo, state.timezone);
  const fmt = (value: { year: number; month: number; day: number }) =>
    new Date(Date.UTC(value.year, value.month - 1, value.day)).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    });
  if (from.year === to.year && from.month === to.month && from.day === to.day) {
    return fmt(from);
  }
  return `${fmt(from)} – ${fmt(to)}`;
}

export function DateRangeSelector({ className }: { className?: string }) {
  const range = useDateRange();
  const [open, setOpen] = useState(false);
  const [customOpen, setCustomOpen] = useState(!range.preset);
  const fromParts = calendarDateFromInstant(range.dateFrom, range.timezone);
  const toParts = calendarDateFromInstant(range.dateTo, range.timezone);
  const [customFrom, setCustomFrom] = useState(toIsoDate(fromParts.year, fromParts.month, fromParts.day));
  const [customTo, setCustomTo] = useState(toIsoDate(toParts.year, toParts.month, toParts.day));
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const from = calendarDateFromInstant(range.dateFrom, range.timezone);
    const to = calendarDateFromInstant(range.dateTo, range.timezone);
    setCustomFrom(toIsoDate(from.year, from.month, from.day));
    setCustomTo(toIsoDate(to.year, to.month, to.day));
    setCustomOpen(!range.preset);
  }, [range.dateFrom, range.dateTo, range.preset, range.timezone]);

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

  const label = useMemo(() => {
    if (range.preset) return DATE_RANGE_PRESET_LABELS[range.preset];
    return formatCustomLabel(range);
  }, [range]);

  const selectPreset = (preset: DateRangePreset) => {
    range.setPreset(preset);
    setCustomOpen(false);
    setOpen(false);
  };

  const applyCustom = () => {
    if (!customFrom || !customTo) return;
    range.setCustomRange(customFrom, customTo);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Период"
        onClick={() => setOpen((current) => !current)}
        className="flex items-center gap-2 h-9 min-w-[13.75rem] px-3 rounded-md border bg-card text-sm text-muted-foreground hover:bg-muted/50"
      >
        <CalendarDays size={15} />
        <span className="flex-1 truncate text-left text-foreground">{label}</span>
        <ChevronDown size={14} className={cn('shrink-0 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div
          role="listbox"
          aria-label="Период"
          className="absolute right-0 top-full z-30 mt-1 w-[min(calc(100vw-2rem),280px)] ui-card p-1.5 shadow-soft"
        >
          {DATE_RANGE_PRESETS.map((preset) => (
            <button
              key={preset}
              type="button"
              role="option"
              aria-selected={range.preset === preset}
              onClick={() => selectPreset(preset)}
              className={cn(
                'w-full text-left rounded-md px-2.5 py-2 text-sm transition-colors',
                'hover:bg-muted/60',
                range.preset === preset && 'bg-accent text-primary',
              )}
            >
              {DATE_RANGE_PRESET_LABELS[preset]}
            </button>
          ))}
          <button
            type="button"
            role="option"
            aria-selected={!range.preset}
            onClick={() => setCustomOpen(true)}
            className={cn(
              'w-full text-left rounded-md px-2.5 py-2 text-sm transition-colors',
              'hover:bg-muted/60',
              !range.preset && 'bg-accent text-primary',
            )}
          >
            {CUSTOM_RANGE_LABEL}
          </button>
          {customOpen && (
            <div className="mt-1 border-t border-border/70 pt-2 px-1.5 pb-1.5 space-y-2">
              <label className="block text-xs text-muted-foreground">
                С
                <input
                  type="date"
                  value={customFrom}
                  onChange={(event) => setCustomFrom(event.target.value)}
                  className="mt-1 w-full h-9 rounded-md border bg-card px-2 text-sm text-foreground"
                />
              </label>
              <label className="block text-xs text-muted-foreground">
                По
                <input
                  type="date"
                  value={customTo}
                  onChange={(event) => setCustomTo(event.target.value)}
                  className="mt-1 w-full h-9 rounded-md border bg-card px-2 text-sm text-foreground"
                />
              </label>
              <button
                type="button"
                onClick={applyCustom}
                disabled={!customFrom || !customTo}
                className="w-full h-8 rounded-md bg-primary text-primary-foreground text-xs font-medium disabled:opacity-50"
              >
                Применить
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
