import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { Button } from '@/shared/components/Button';

const PRESETS = [
  { id: 'shorter', label: 'Сделать короче', instruction: 'Сделай короче, сохрани смысл.' },
  { id: 'clearer', label: 'Сделать понятнее', instruction: 'Сделай понятнее и конкретнее.' },
  { id: 'selling', label: 'Сделать более продающим', instruction: 'Сделай более продающим для партнёров.' },
  { id: 'tone', label: 'Изменить тон', instruction: 'Сделай тон спокойнее и деловым.' },
];

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
  onGenerate: (instruction: string) => void;
  onAccept: () => void;
  onCancel: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState('');

  return (
    <div className="relative shrink-0">
      <button
        type="button"
        className="inline-flex h-7 items-center gap-1 text-[11px] font-medium text-primary whitespace-nowrap hover:underline disabled:opacity-50"
        disabled={pending}
        onClick={() => setOpen((value) => !value)}
      >
        <Sparkles size={11} aria-hidden />
        {pending ? 'AI...' : 'Улучшить с AI'}
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-72 ui-card p-3 space-y-2 shadow-soft">
          <p className="text-xs font-medium flex items-center gap-1">
            <Sparkles size={12} />
            Улучшить текст
          </p>
          <div className="flex flex-wrap gap-1">
            {PRESETS.map((item) => (
              <button
                key={item.id}
                type="button"
                disabled={pending}
                className="px-2 py-1 rounded-md text-[11px] border border-border hover:bg-muted"
                onClick={() => onGenerate(item.instruction)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <textarea
            className="ui-input min-h-[64px] h-auto py-1.5 text-xs resize-y"
            placeholder="Своя инструкция"
            value={custom}
            disabled={pending}
            onChange={(e) => setCustom(e.target.value)}
          />
          <div className="flex justify-end gap-1">
            <Button type="button" size="sm" variant="ghost" onClick={() => { setOpen(false); onCancel(); }}>
              Закрыть
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={pending || !custom.trim()}
              onClick={() => onGenerate(custom.trim())}
            >
              {pending ? 'Генерация...' : 'Применить'}
            </Button>
          </div>
          {error && <p className="text-xs text-destructive">{error}</p>}
          {proposed != null && (
            <div className="space-y-2 border-t border-border pt-2">
              <p className="text-xs text-muted-foreground whitespace-pre-wrap">{proposed}</p>
              <Button type="button" size="sm" onClick={() => { onAccept(); setOpen(false); }}>
                Принять
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
