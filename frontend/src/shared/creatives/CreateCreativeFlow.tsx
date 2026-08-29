import { useEffect, useRef, useState, type ReactNode } from 'react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { aiErrorMessage } from '@/shared/ai/messages';
import { cn } from '@/shared/utils/cn';
import {
  BANNER_FORMATS,
  CHANNELS,
  CREATIVE_TYPES,
  GOALS,
  STYLES,
  VARIANT_KIND_LABELS,
  formatCreativeText,
} from './labels';
import type { BannerFormat, CreativeType, CreativeVariant, GenerationResponse } from './types';

type Phase = 'type' | 'settings' | 'generating' | 'processing' | 'review' | 'error';

interface Props {
  offerId: string;
  apiBase: string;
  onClose: () => void;
  onSaved: () => void;
}

export function CreateCreativeFlow({ offerId, apiBase, onClose, onSaved }: Props) {
  const [phase, setPhase] = useState<Phase>('type');
  const [type, setType] = useState<CreativeType>('text');
  const [channel, setChannel] = useState('telegram');
  const [goal, setGoal] = useState('sale');
  const [style, setStyle] = useState('neutral');
  const [format, setFormat] = useState<BannerFormat>('square_1_1');
  const [instruction, setInstruction] = useState('');
  const [variantsCount, setVariantsCount] = useState(3);
  const [generation, setGeneration] = useState<GenerationResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<CreativeVariant | null>(null);
  const inFlight = useRef(false);

  useEffect(() => {
    if (phase !== 'processing' || !generation?.generation_id) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.get<GenerationResponse>(`/ai/generations/${generation.generation_id}`);
        if (next.status === 'completed') {
          setGeneration(next);
          setPhase('review');
        } else if (next.status === 'failed') {
          setError(aiErrorMessage({ error: next.error || { code: 'AI_UNAVAILABLE', message: '' } }));
          setPhase('error');
        }
      } catch (err) {
        setError(aiErrorMessage(err));
        setPhase('error');
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [phase, generation?.generation_id]);

  const generate = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    setPhase(type === 'banner' ? 'processing' : 'generating');
    try {
      const body =
        type === 'banner'
          ? { type, format, instruction, variants: 1 }
          : {
              type,
              channel,
              goal,
              style,
              instruction,
              variants: type === 'text' ? variantsCount : Math.min(variantsCount, 3),
            };
      const result = await api.post<GenerationResponse>(`${apiBase}/${offerId}/creatives/generate`, body);
      setGeneration(result);
      if (result.status === 'completed') setPhase('review');
      else if (result.status === 'failed') {
        setError(aiErrorMessage({ error: result.error || { code: 'AI_UNAVAILABLE', message: '' } }));
        setPhase('error');
      }
    } catch (err) {
      setError(aiErrorMessage(err));
      setPhase('error');
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  };

  const saveVariant = async (variant: CreativeVariant, index: number) => {
    if (inFlight.current || !generation) return;
    inFlight.current = true;
    setBusy(true);
    try {
      await api.post(`${apiBase}/${offerId}/creatives`, {
        generation_id: generation.generation_id,
        variant_index: index,
        headline: variant.headline,
        body: variant.body,
        cta: variant.cta,
        hashtags: variant.hashtags,
      });
      onSaved();
    } catch (err) {
      setError(aiErrorMessage(err, 'Не удалось сохранить материал'));
      setPhase('error');
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/30">
      <div className="ui-card w-full max-w-2xl max-h-[88vh] flex flex-col shadow-soft">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border/70">
          <h3 className="ui-section-title">Создать материал</h3>
          <button type="button" className="text-sm text-muted-foreground hover:text-foreground" onClick={onClose}>
            Закрыть
          </button>
        </div>
        <div className="overflow-auto p-5 space-y-4">
          {phase === 'type' && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Что создать?</p>
              {CREATIVE_TYPES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setType(item.value)}
                  className={cn(
                    'w-full text-left rounded-lg border px-4 py-3',
                    type === item.value ? 'border-primary bg-accent' : 'border-border/70',
                  )}
                >
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{item.hint}</p>
                </button>
              ))}
            </div>
          )}

          {phase === 'settings' && (
            <div className="space-y-3">
              {type !== 'banner' && (
                <>
                  <Field label="Канал">
                    <select className="ui-input" value={channel} onChange={(e) => setChannel(e.target.value)}>
                      {CHANNELS.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Цель">
                    <select className="ui-input" value={goal} onChange={(e) => setGoal(e.target.value)}>
                      {GOALS.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Стиль">
                    <select className="ui-input" value={style} onChange={(e) => setStyle(e.target.value)}>
                      {STYLES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Количество вариантов">
                    <select
                      className="ui-input"
                      value={variantsCount}
                      onChange={(e) => setVariantsCount(Number(e.target.value))}
                    >
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                      <option value={3}>3</option>
                    </select>
                  </Field>
                </>
              )}
              {type === 'banner' && (
                <Field label="Формат">
                  <select
                    className="ui-input"
                    value={format}
                    onChange={(e) => setFormat(e.target.value as BannerFormat)}
                  >
                    {BANNER_FORMATS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label} · {item.hint}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              <Field label="Дополнительная инструкция">
                <textarea
                  className="ui-input min-h-[96px]"
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  placeholder="Например: сделай акцент на простоте использования"
                />
              </Field>
            </div>
          )}

          {(phase === 'generating' || phase === 'processing') && (
            <div className="py-10 flex flex-col items-center gap-3 text-sm text-muted-foreground">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
              {phase === 'processing' ? 'Генерируем баннер…' : 'AI готовит варианты…'}
            </div>
          )}

          {phase === 'review' && (
            <div className="space-y-3">
              {(generation?.variants || []).map((variant, index) => (
                <div key={index} className="rounded-lg border border-border/70 p-3 space-y-2">
                  {variant.kind && (
                    <p className="text-xs text-muted-foreground">{VARIANT_KIND_LABELS[variant.kind] || variant.kind}</p>
                  )}
                  {variant.asset_id ? (
                    <p className="text-sm">Баннер готов. Можно сохранить черновик и скачать после сохранения.</p>
                  ) : editing === variant ? (
                    <div className="space-y-2">
                      <input
                        className="ui-input"
                        value={editing.headline || ''}
                        onChange={(e) => setEditing({ ...editing, headline: e.target.value })}
                      />
                      <textarea
                        className="ui-input min-h-[88px]"
                        value={editing.body || ''}
                        onChange={(e) => setEditing({ ...editing, body: e.target.value })}
                      />
                      <input
                        className="ui-input"
                        value={editing.cta || ''}
                        onChange={(e) => setEditing({ ...editing, cta: e.target.value })}
                      />
                    </div>
                  ) : (
                    <pre className="text-sm whitespace-pre-wrap font-sans">{formatCreativeText(variant)}</pre>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" disabled={busy} onClick={() => saveVariant(editing === variant ? editing : variant, index)}>
                      Выбрать
                    </Button>
                    {!variant.asset_id && (
                      <Button size="sm" variant="secondary" onClick={() => setEditing(variant)}>
                        Редактировать
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {phase === 'error' && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <div className="px-5 py-4 border-t border-border/70 flex justify-end gap-2">
          {phase === 'type' && (
            <Button onClick={() => setPhase('settings')}>Далее</Button>
          )}
          {phase === 'settings' && (
            <>
              <Button variant="ghost" onClick={() => setPhase('type')}>
                Назад
              </Button>
              <Button disabled={busy} onClick={generate}>
                Создать
              </Button>
            </>
          )}
          {(phase === 'review' || phase === 'error') && (
            <Button variant="secondary" disabled={busy} onClick={() => setPhase('settings')}>
              Создать ещё
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="ui-label">{label}</span>
      {children}
    </label>
  );
}
