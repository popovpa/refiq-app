import { Check, ChevronDown, Search, X } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
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
            value === option.value ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
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
                ? 'bg-primary text-primary-foreground border-primary'
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
  onStep,
}: {
  steps: Array<{ id: string; label: string }>;
  current: string;
  onStep?: (id: string) => void;
}) {
  const currentIndex = steps.findIndex((step) => step.id === current);
  return (
    <ol className="flex flex-wrap gap-2">
      {steps.map((step, index) => {
        const done = index < currentIndex;
        const active = step.id === current;
        return (
          <li key={step.id}>
            <button
              type="button"
              disabled={!onStep || index > currentIndex}
              onClick={() => onStep?.(step.id)}
              className={cn(
                'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                active && 'border-primary bg-accent text-primary',
                done && 'border-border text-foreground',
                !active && !done && 'border-border text-muted-foreground',
                onStep && index <= currentIndex && 'hover:border-primary/40',
              )}
            >
              <span className="tabular-nums">{index + 1}</span>
              {step.label}
            </button>
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
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  extra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <label className="text-sm font-medium">
          {label}
          {required ? ' *' : ''}
        </label>
        {extra}
      </div>
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
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
