import { Check, ChevronDown, Search, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { categoryLabel, findVertical, searchCategories } from '@/shared/catalog/categories';
import { countryByCode, countryFlag, searchCountries } from '@/shared/catalog/countries';
import { cn } from '@/shared/utils/cn';

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
            value === option.value ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function SelectableCard({
  selected,
  title,
  description,
  onClick,
  badge,
}: {
  selected: boolean;
  title: string;
  description: string;
  onClick: () => void;
  badge?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'text-left rounded-xl border p-4 transition-colors',
        selected ? 'border-primary bg-accent/40 ring-1 ring-primary/20' : 'border-border bg-card hover:border-primary/30',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium text-sm">{title}</p>
        {badge && <span className="ui-badge bg-accent text-primary text-[10px]">{badge}</span>}
        {selected && <Check size={16} className="text-primary shrink-0" />}
      </div>
      <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">{description}</p>
    </button>
  );
}

export function CheckboxCard({
  checked,
  label,
  description,
  onChange,
  aiRecommended,
}: {
  checked: boolean;
  label: string;
  description?: string;
  onChange: () => void;
  aiRecommended?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onChange}
      className={cn(
        'text-left rounded-xl border p-3 transition-colors',
        checked ? 'border-primary bg-accent/30' : 'border-border bg-card hover:border-primary/20',
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'h-4 w-4 rounded border flex items-center justify-center shrink-0',
            checked ? 'bg-primary border-primary text-primary-foreground' : 'border-border',
          )}
        >
          {checked && <Check size={10} />}
        </span>
        <span className="text-sm font-medium">{label}</span>
        {aiRecommended && <span className="ui-badge bg-accent text-primary text-[10px] ml-auto">AI</span>}
      </div>
      {description && <p className="text-xs text-muted-foreground mt-1.5 pl-6">{description}</p>}
    </button>
  );
}

export function ChipSelect({
  value,
  options,
  onChange,
  allowCustom,
  customValue,
  onCustomChange,
  customLabel = 'Свой',
}: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  allowCustom?: boolean;
  customValue?: string;
  onCustomChange?: (value: string) => void;
  customLabel?: string;
}) {
  const isCustom = allowCustom && value !== '' && !options.some((item) => item.value === value);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium border transition-colors',
              value === option.value && !isCustom
                ? 'bg-accent text-primary border-primary'
                : 'bg-card text-muted-foreground border-border hover:text-foreground',
            )}
          >
            {option.label}
          </button>
        ))}
        {allowCustom && (
          <button
            type="button"
            onClick={() => {
              const next =
                customValue && !options.some((item) => item.value === customValue) ? customValue : '1';
              onCustomChange?.(next);
              onChange(next);
            }}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium border transition-colors',
              isCustom ? 'bg-primary text-primary-foreground border-primary' : 'bg-card text-muted-foreground border-border',
            )}
          >
            {customLabel}
          </button>
        )}
      </div>
      {allowCustom && isCustom && (
        <input
          className="ui-input max-w-[120px]"
          type="number"
          min={1}
          placeholder="Дней"
          value={customValue || ''}
          onChange={(e) => onCustomChange?.(e.target.value)}
        />
      )}
    </div>
  );
}

export function SearchableCombobox({
  value,
  options,
  onChange,
  placeholder = 'Выберите...',
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const filtered = useMemo(
    () => options.filter((item) => item.toLowerCase().includes(query.trim().toLowerCase())),
    [options, query],
  );

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="ui-input flex items-center justify-between gap-2 text-left"
        onClick={() => setOpen((current) => !current)}
      >
        <span className={cn(!value && 'text-muted-foreground')}>{value || placeholder}</span>
        <ChevronDown size={16} className="text-muted-foreground shrink-0" />
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-full ui-card border shadow-soft p-2 space-y-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              className="ui-input pl-8 h-9"
              placeholder="Поиск..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          <ul className="max-h-48 overflow-auto space-y-0.5">
            {filtered.map((item) => (
              <li key={item}>
                <button
                  type="button"
                  className={cn(
                    'w-full text-left px-2 py-1.5 rounded-md text-sm hover:bg-muted',
                    item === value && 'bg-accent text-primary font-medium',
                  )}
                  onClick={() => {
                    onChange(item);
                    setOpen(false);
                    setQuery('');
                  }}
                >
                  {item}
                </button>
              </li>
            ))}
            {filtered.length === 0 && <li className="px-2 py-1.5 text-sm text-muted-foreground">Ничего не найдено</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

export function GeoCombobox({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return <SearchableCombobox value={value} options={options} onChange={onChange} placeholder="Выберите регион" />;
}

export function WizardStepper({
  steps,
  current,
  reachable,
  onStep,
}: {
  steps: Array<{ id: string; label: string }>;
  current: string;
  reachable?: string[];
  onStep?: (id: string) => void;
}) {
  const currentIndex = steps.findIndex((step) => step.id === current);
  return (
    <ol className="flex w-full items-center">
      {steps.map((step, index) => {
        const done = index < currentIndex;
        const active = step.id === current;
        const canOpen = Boolean(onStep && (reachable ? reachable.includes(step.id) : index <= currentIndex));
        return (
          <li key={step.id} className={cn('flex items-center', index < steps.length - 1 && 'flex-1')}>
            <button
              type="button"
              disabled={!canOpen}
              onClick={() => canOpen && onStep?.(step.id)}
              className="flex items-center gap-2 min-w-0"
            >
              <span
                className={cn(
                  'h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0',
                  (active || done) && 'bg-primary text-primary-foreground',
                  !active && !done && 'bg-muted text-muted-foreground',
                )}
              >
                {done ? <Check size={14} /> : index + 1}
              </span>
              <span
                className={cn(
                  'text-sm font-medium whitespace-nowrap',
                  active ? 'text-foreground' : done ? 'text-foreground' : 'text-muted-foreground',
                )}
              >
                {step.label}
              </span>
            </button>
            {index < steps.length - 1 && (
              <span className={cn('mx-3 h-px flex-1', index < currentIndex ? 'bg-primary' : 'bg-border')} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function FieldShell({
  label,
  required,
  hint,
  error,
  extra,
  fill,
  className,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  extra?: ReactNode;
  fill?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn('space-y-1.5', fill && 'flex h-full min-h-0 flex-col', className)}>
      <div className="flex min-h-7 items-center justify-between gap-2">
        <label className="text-sm font-medium">
          {label}
          {required ? ' *' : ''}
        </label>
        {extra}
      </div>
      <div className={cn(fill && 'flex min-h-0 flex-1 flex-col h-full')}>{children}</div>
      {error ? <p className="text-xs text-destructive">{error}</p> : hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function SiteCombobox({
  value,
  onChange,
  sites,
}: {
  value: string;
  onChange: (value: string) => void;
  sites?: Array<{ id: number | string; domain: string }>;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const list = sites ?? [];

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <div className="relative">
        <input
          className="ui-input pr-9"
          placeholder="python-academy.com"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={() => list.length > 0 && setOpen(true)}
        />
        <button
          type="button"
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground"
          aria-label="Показать сайты"
          onClick={() => setOpen((current) => !current)}
        >
          <ChevronDown size={16} />
        </button>
      </div>
      {open && (
        <ul className="absolute z-30 mt-1 max-h-48 w-full overflow-auto ui-card border p-1 shadow-soft">
          {list.length === 0 && (
            <li className="px-2 py-1.5 text-sm text-muted-foreground">Нет подключённых сайтов</li>
          )}
          {list.map((site) => (
            <li key={site.id}>
              <button
                type="button"
                className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onChange(`https://${site.domain}`);
                  setOpen(false);
                }}
              >
                {site.domain}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ChipRemovable({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-accent text-primary">
      {label}
      <button type="button" onClick={onRemove} aria-label={`Убрать ${label}`}>
        <X size={12} />
      </button>
    </span>
  );
}

export function CategoryCombobox({
  value,
  onChange,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  error?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const filtered = useMemo(() => searchCategories(query), [query]);
  const grouped = useMemo(() => {
    const groups: Array<{ vertical: string; items: ReturnType<typeof searchCategories> }> = [];
    const seen = new Map<string, number>();
    filtered.forEach((item) => {
      const vertical = findVertical(item.verticalCode)?.nameRu || item.verticalCode;
      const index = seen.get(vertical);
      if (index == null) {
        seen.set(vertical, groups.length);
        groups.push({ vertical, items: [item] });
      } else {
        groups[index].items.push(item);
      }
    });
    return groups;
  }, [filtered]);
  const flat = filtered;

  return (
    <div className="relative">
      <button
        type="button"
        className={cn('ui-input flex items-center justify-between gap-2 text-left', error && 'border-destructive')}
        onClick={() => setOpen((current) => !current)}
      >
        <span className={cn('truncate', !value && 'text-muted-foreground')}>
          {value ? categoryLabel(value) : 'Выберите категорию'}
        </span>
        <ChevronDown size={16} className="text-muted-foreground shrink-0" />
      </button>
      {open && (
        <div className="absolute z-30 mt-1 w-full ui-card border shadow-soft p-2 space-y-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              className="ui-input pl-8 h-9"
              placeholder="Поиск..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setActive(0);
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') {
                  e.preventDefault();
                  setActive((index) => Math.min(index + 1, flat.length - 1));
                }
                if (e.key === 'ArrowUp') {
                  e.preventDefault();
                  setActive((index) => Math.max(index - 1, 0));
                }
                if (e.key === 'Enter' && flat[active]) {
                  e.preventDefault();
                  onChange(flat[active].code);
                  setOpen(false);
                  setQuery('');
                }
                if (e.key === 'Escape') setOpen(false);
              }}
              autoFocus
            />
          </div>
          <ul className="max-h-52 overflow-auto space-y-1">
            {grouped.map((group) => (
              <li key={group.vertical}>
                <p className="px-2 py-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                  {group.vertical}
                </p>
                {group.items.map((item) => {
                  const index = flat.findIndex((entry) => entry.code === item.code);
                  return (
                    <button
                      key={item.code}
                      type="button"
                      className={cn(
                        'w-full text-left px-2 py-1.5 rounded-md text-sm hover:bg-muted',
                        item.code === value && 'bg-accent text-primary font-medium',
                        index === active && 'bg-muted',
                      )}
                      onClick={() => {
                        onChange(item.code);
                        setOpen(false);
                        setQuery('');
                      }}
                    >
                      {item.nameRu}
                    </button>
                  );
                })}
              </li>
            ))}
            {flat.length === 0 && <li className="px-2 py-1.5 text-sm text-muted-foreground">Ничего не найдено</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

export function CountryMultiSelect({
  value,
  onChange,
  error,
}: {
  value: string[];
  onChange: (value: string[]) => void;
  error?: boolean;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const selected = useMemo(() => new Set(value), [value]);
  const options = useMemo(() => searchCountries(query), [query]);

  const toggle = (code: string) => {
    if (selected.has(code)) onChange(value.filter((item) => item !== code));
    else onChange([...value, code]);
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          className={cn('ui-input pl-8 h-9', error && 'border-destructive')}
          placeholder="Поиск по странам..."
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setActive((index) => Math.min(index + 1, options.length - 1));
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActive((index) => Math.max(index - 1, 0));
            }
            if (e.key === 'Enter' && options[active]) {
              e.preventDefault();
              toggle(options[active].code);
            }
            if (e.key === 'Escape') setOpen(false);
          }}
        />
        {open && (
          <ul className="absolute z-30 mt-1 w-full max-h-48 overflow-auto ui-card border shadow-soft p-1">
            {options.slice(0, 80).map((country, index) => {
              const checked = selected.has(country.code);
              return (
                <li key={country.code}>
                  <button
                    type="button"
                    className={cn(
                      'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-muted',
                      index === active && 'bg-muted',
                    )}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => toggle(country.code)}
                  >
                    <span
                      className={cn(
                        'h-4 w-4 rounded border flex items-center justify-center shrink-0',
                        checked ? 'bg-primary border-primary text-primary-foreground' : 'border-border',
                      )}
                    >
                      {checked && <Check size={10} />}
                    </span>
                    <span aria-hidden>{countryFlag(country.code)}</span>
                    <span>{country.nameRu}</span>
                  </button>
                </li>
              );
            })}
            {options.length === 0 && <li className="px-2 py-1.5 text-sm text-muted-foreground">Ничего не найдено</li>}
          </ul>
        )}
      </div>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((code) => (
            <ChipRemovable
              key={code}
              label={`${countryFlag(code)} ${countryByCode(code)?.nameRu || code}`}
              onRemove={() => toggle(code)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
