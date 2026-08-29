import { useEffect, useState } from 'react';
import { Check, ChevronRight, Sparkles } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { CATEGORIES } from '@/shared/offers/labels';

const EXAMPLE =
  'Онлайн-курс Python для начинающих. Стоимость 30 000 ₽. Хотим платить партнёрам за подтверждённую покупку.';

const PREPARES = [
  'название и описание',
  'целевое действие',
  'модель и размер вознаграждения',
  'окно атрибуции',
  'доступ и GEO',
];

const TIPS = [
  'что вы продаёте;',
  'кто является вашим клиентом;',
  'стоимость продукта, если она известна;',
  'какое целевое действие важно;',
  'особенности партнёрской программы.',
];

export function AiDraftBrief({
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  pending: boolean;
  error: string | null;
  onSubmit: (payload: { description: string; category?: string; product_url?: string }) => void;
  onCancel: () => void;
}) {
  const [description, setDescription] = useState('');
  const [productUrl, setProductUrl] = useState('');
  const [category, setCategory] = useState('');
  const [exampleOpen, setExampleOpen] = useState(false);
  const stage = useGenerationStage(pending, Boolean(productUrl.trim()));

  return (
    <div className="mx-auto w-full max-w-[1120px] space-y-4">
      <button type="button" onClick={onCancel} className="text-sm text-muted-foreground hover:text-primary">
        ← Офферы
      </button>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-primary" />
          <h1 className="ui-page-title">Создать с AI</h1>
        </div>
        <p className="text-sm text-muted-foreground max-w-2xl">
          Опишите продукт своими словами. AI подготовит черновик оффера — вы сможете проверить и изменить его перед
          созданием.
        </p>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,13fr)_minmax(240px,7fr)]">
        <div className="ui-card p-4 space-y-3 min-w-0">
          <label className="block">
            <span className="ui-label">Что вы хотите продвигать? *</span>
            <textarea
              className="ui-input min-h-[160px] h-auto py-2 resize-y"
              placeholder="Например: онлайн-курс английского языка для IT-специалистов. Стоимость 30 000 рублей."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={pending}
            />
          </label>
          <div>
            <button
              type="button"
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              onClick={() => setExampleOpen((value) => !value)}
            >
              Пример описания
              <ChevronRight size={14} className={exampleOpen ? 'rotate-90 transition-transform' : 'transition-transform'} />
            </button>
            {exampleOpen && (
              <button
                type="button"
                className="mt-2 block w-full text-left rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
                disabled={pending}
                onClick={() => {
                  setDescription(EXAMPLE);
                  setExampleOpen(false);
                }}
              >
                {EXAMPLE}
              </button>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1.4fr)_minmax(160px,0.8fr)]">
            <label className="block min-w-0">
              <span className="ui-label">Ссылка на продукт</span>
              <input
                className="ui-input"
                placeholder="https://"
                value={productUrl}
                onChange={(e) => setProductUrl(e.target.value)}
                disabled={pending}
              />
              <p className="mt-1.5 text-xs text-muted-foreground">
                AI может использовать публичную информацию с этой страницы, чтобы точнее подготовить черновик.
              </p>
            </label>
            <label className="block min-w-0">
              <span className="ui-label">Категория</span>
              <select
                className="ui-input"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={pending}
              >
                <option value="">Не указана</option>
                {CATEGORIES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {pending && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary shrink-0" />
              {stage}
            </div>
          )}
          <div className="flex flex-wrap gap-2 pt-1">
            <Button variant="ghost" type="button" disabled={pending} onClick={onCancel}>
              Отмена
            </Button>
            <Button
              type="button"
              disabled={pending || !description.trim()}
              onClick={() =>
                onSubmit({
                  description: description.trim(),
                  category: category || undefined,
                  product_url: productUrl.trim() || undefined,
                })
              }
            >
              {pending ? 'Создаём черновик...' : 'Создать черновик'}
            </Button>
          </div>
        </div>

        <aside className="ui-card p-4 space-y-4 min-w-0">
          <div>
            <h2 className="ui-section-title flex items-center gap-2">
              <Sparkles size={14} className="text-primary" />
              Что подготовит AI
            </h2>
            <p className="text-sm text-muted-foreground mt-2">AI сформирует черновик:</p>
            <ul className="mt-2 space-y-1.5">
              {PREPARES.map((item) => (
                <li key={item} className="flex items-start gap-2 text-sm">
                  <Check size={14} className="text-success mt-0.5 shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
            <p className="text-xs text-muted-foreground mt-3">
              Вы сможете проверить и изменить все параметры перед публикацией.
            </p>
          </div>
          <div className="border-t border-border/70 pt-3">
            <h3 className="text-sm font-medium">Как получить лучший результат</h3>
            <p className="text-sm text-muted-foreground mt-2">Для более точного результата укажите:</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {TIPS.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}

function useGenerationStage(pending: boolean, hasUrl: boolean) {
  const [stage, setStage] = useState('Анализируем описание...');

  useEffect(() => {
    if (!pending) {
      setStage('Анализируем описание...');
      return;
    }
    setStage('Анализируем описание...');
    const steps = hasUrl
      ? [
          [900, 'Получаем информацию о продукте...'] as const,
          [2400, 'Подготавливаем черновик...'] as const,
        ]
      : [[1200, 'Подготавливаем черновик...'] as const];
    const timers = steps.map(([delay, text]) => window.setTimeout(() => setStage(text), delay));
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [pending, hasUrl]);

  return stage;
}
