import { useState } from 'react';
import { Sparkles, X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import {
  AI_REWRITE_PRESETS,
  type AiGuidancePresetId,
  type AiRewriteRequest,
} from '@/shared/ai/presets';

export function AiRewriteControl({
  pending,
  error,
  proposed,
  onGenerate,
  onAccept,
  onCancel,
}: {
  pending: boolean;
  error: string | null;
  proposed: string | null;
  onGenerate: (request: AiRewriteRequest) => void;
  onAccept: () => void;
  onCancel: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [preset, setPreset] = useState<AiGuidancePresetId | undefined>();

  const close = () => {
    setOpen(false);
    setPreset(undefined);
    onCancel();
  };

  const apply = () => {
    if (proposed == null || pending) return;
    onAccept();
    setOpen(false);
    setPreset(undefined);
  };

  return (
    <div className="shrink-0">
      <button
        type="button"
        className="inline-flex h-7 items-center gap-1 text-[11px] font-medium text-primary whitespace-nowrap hover:underline"
        onClick={() => setOpen(true)}
      >
        <Sparkles size={11} aria-hidden />
        Улучшить с AI
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-foreground/30" onClick={pending ? undefined : close} />
          <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="ui-section-title flex items-center gap-2">
                  <Sparkles size={16} className="text-primary" aria-hidden />
                  Улучшить с помощью AI
                </h2>
                <p className="text-sm text-muted-foreground mt-1">Выберите тип улучшения текста</p>
              </div>
              <button
                type="button"
                onClick={close}
                disabled={pending}
                className="text-muted-foreground hover:text-foreground disabled:opacity-50"
              >
                <X size={18} />
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              {AI_REWRITE_PRESETS.map((item) => {
                const active = preset === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    disabled={pending}
                    className={
                      active
                        ? 'px-3 py-1.5 rounded-md text-xs font-medium border border-primary bg-brand-soft text-brand'
                        : 'px-3 py-1.5 rounded-md text-xs font-medium border border-border hover:bg-muted disabled:opacity-50'
                    }
                    onClick={() => {
                      setPreset(item.id);
                      onGenerate({ preset: item.id });
                    }}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>

            {pending ? (
              <div className="flex items-start gap-3 rounded-md border border-border bg-muted/40 px-3 py-3">
                <div className="mt-0.5 animate-spin rounded-full h-4 w-4 border-b-2 border-primary shrink-0" />
                <div>
                  <p className="text-sm font-medium">Генерируем вариант...</p>
                  <p className="text-sm text-muted-foreground">Это займёт несколько секунд.</p>
                </div>
              </div>
            ) : null}

            {error ? (
              <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            ) : null}

            {proposed != null && !pending ? (
              <div className="space-y-2">
                <p className="ui-label">Результат</p>
                <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-sm whitespace-pre-wrap">
                  {proposed}
                </div>
              </div>
            ) : null}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" disabled={pending} onClick={close}>
                Закрыть
              </Button>
              <Button type="button" disabled={pending || proposed == null} onClick={apply}>
                Применить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
