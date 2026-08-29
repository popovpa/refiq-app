import { Sparkles } from 'lucide-react';

export function OfferFormSection({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="ui-card p-4 space-y-3">
      <h2 className="ui-section-title flex items-center gap-2">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-md bg-accent text-[11px] font-semibold text-primary">
          {n}
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

export function OfferAiFieldBadge({
  variant = 'recommendation',
}: {
  variant?: 'recommendation' | 'applied' | 'website';
}) {
  const label =
    variant === 'applied' ? 'изменено AI' : variant === 'website' ? 'Найдено на сайте' : 'рекомендация AI';
  return (
    <span className="ui-badge shrink-0 bg-accent text-primary gap-1 px-1.5 py-0 text-[11px] font-medium leading-5 whitespace-nowrap">
      <Sparkles size={11} aria-hidden />
      {label}
    </span>
  );
}

export function OfferField({
  label,
  required,
  error,
  hint,
  extra,
  aiMark,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  extra?: React.ReactNode;
  aiMark?: 'generated' | 'recommended' | 'applied';
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between gap-2 h-7 mb-1.5">
        <span className="min-w-0 truncate text-sm font-medium text-foreground" title={label}>
          {label}
          {required ? ' *' : ''}
        </span>
        {(aiMark || extra) && (
          <span className="flex items-center gap-1.5 shrink-0">
            {aiMark ? <OfferAiFieldBadge variant={aiMark === 'applied' ? 'applied' : 'recommendation'} /> : null}
            {extra}
          </span>
        )}
      </div>
      {children}
      {error ? (
        <p className="mt-1 text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

