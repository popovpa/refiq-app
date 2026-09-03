import { useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ChevronDown, Sparkles, Upload, X } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { AiDraftBrief } from '@/shared/ai/AiDraftBrief';
import { AiRewriteControl } from '@/shared/ai/AiRewriteControl';
import { aiErrorMessage } from '@/shared/ai/messages';
import { toAiRewritePayload, type AiRewriteRequest } from '@/shared/ai/presets';
import { draftMarks, draftToForm, mergeAiDraftIntoForm } from '@/shared/ai/offerDraft';
import type { AiMarkedFields, AiRewriteField, OfferAiDraftResponse, OfferAiRewriteResponse } from '@/shared/ai/types';
import { CATEGORIES, GEO_OPTIONS } from '@/shared/offers/labels';
import { DESCRIPTION_MAX, offerFormErrors } from '@/shared/offers/offerFormMeta';
import { OfferAiFieldBadge } from '@/shared/offers/OfferFormSection';
import { formToPayload, blankOfferForm, type OfferFormValues } from '@/shared/offers/types';
import {
  ACCESS_CARDS,
  ATTRIBUTION_PRESETS,
  CONVERSION_GOAL_CARDS,
  RESTRICTION_PRESETS,
  TRAFFIC_SOURCE_CARDS,
  WIZARD_STEPS,
  commissionExample,
  type WizardStepId,
} from '@/shared/offers/wizard/meta';
import { OfferWizardPreview, OfferWizardReadiness } from '@/shared/offers/wizard/OfferWizardPanels';
import { canPublishOffer } from '@/shared/offers/wizard/readiness';
import {
  CheckboxCard,
  ChipSelect,
  FieldShell,
  GeoCombobox,
  SearchableCombobox,
  SegmentedControl,
  SelectableCard,
  WizardStepper,
} from '@/shared/offers/wizard/ui';
import { OfferImage } from '@/shared/offers/OfferImage';
import type { BusinessSite } from '@/pages/business/settings/types';
import { resizeImage } from '@/shared/utils/image';
import { cn } from '@/shared/utils/cn';

type Phase = 'ai-brief' | 'wizard';

function resolveInitialPhase(initialAiBrief: boolean): Phase {
  return initialAiBrief ? 'ai-brief' : 'wizard';
}

export function OfferWizard({
  initialAiBrief = false,
  onBack,
  onCreated,
}: {
  initialAiBrief?: boolean;
  onBack: () => void;
  onCreated: (id: string) => void;
}) {
  const { addToast } = useToast();
  const [phase, setPhase] = useState<Phase>(() => resolveInitialPhase(initialAiBrief));
  const [step, setStep] = useState<WizardStepId>('product');
  const [form, setForm] = useState<OfferFormValues>(() => blankOfferForm());
  const [aiMarked, setAiMarked] = useState<AiMarkedFields>({});
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [attempted, setAttempted] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [rewrite, setRewrite] = useState<{ field: AiRewriteField; proposed: string | null; error: string | null } | null>(null);
  const [imageFromWebsite, setImageFromWebsite] = useState(false);
  const imageRef = useRef<HTMLInputElement>(null);

  const { data: sites } = useQuery<BusinessSite[]>({
    queryKey: ['business', 'sites'],
    queryFn: () => api.get('/business/sites'),
  });

  const createOffer = useMutation({
    mutationFn: (status: 'draft' | 'active') => api.post<{ id: string }>('/business/offers', formToPayload(form, status)),
    onSuccess: async (data, status) => {
      if (generationId) {
        await api.post(`/ai/generations/${generationId}/feedback`, { outcome: 'EDITED_AFTER_GENERATION' }).catch(() => undefined);
      }
      addToast(status === 'active' ? 'Оффер опубликован' : 'Черновик сохранён', 'success');
      onCreated(data.id);
    },
    onError: () => addToast('Не удалось сохранить оффер', 'error'),
  });

  const generateDraft = useMutation({
    mutationFn: (payload: { description: string; category?: string; product_url?: string }) =>
      api.post<OfferAiDraftResponse>('/ai/offers/draft', payload),
    onSuccess: (data) => {
      setForm(draftToForm(data.draft, data.recommendations, data.image_url));
      setAiMarked(draftMarks());
      setGenerationId(data.generation_id);
      setImageFromWebsite(Boolean(data.image_url));
      setBriefError(null);
      setPhase('wizard');
      setStep('product');
    },
    onError: (error) => setBriefError(aiErrorMessage(error)),
  });

  const fillMissing = useMutation({
    mutationFn: () => {
      const description = [
        form.name && `Название: ${form.name}`,
        form.description && `Описание: ${form.description}`,
        form.product_url && `Сайт: ${form.product_url}`,
        `Комиссия: ${form.commission_value} ${form.commission_type}`,
      ]
        .filter(Boolean)
        .join('\n');
      return api.post<OfferAiDraftResponse>('/ai/offers/draft', {
        description: description || 'Заполни недостающие поля оффера',
        category: form.category || undefined,
        product_url: form.product_url || undefined,
      });
    },
    onSuccess: (data) => {
      setForm(mergeAiDraftIntoForm(form, data.draft, data.recommendations, data.image_url, true));
      setAiMarked((current) => ({ ...current, ...draftMarks() }));
      setGenerationId(data.generation_id);
      addToast('Недостающие поля заполнены', 'success');
    },
    onError: (error) => addToast(aiErrorMessage(error), 'error'),
  });

  const rewriteField = useMutation({
    mutationFn: ({ field, request }: { field: AiRewriteField; request: AiRewriteRequest }) =>
      api.post<OfferAiRewriteResponse>(`/ai/offers/fields/${field}/rewrite`, {
        ...toAiRewritePayload(request),
        value: form[field],
        context: form,
      }),
    onSuccess: (data) => setRewrite({ field: data.field as AiRewriteField, proposed: data.value, error: null }),
    onError: (error, variables) =>
      setRewrite({ field: variables.field, proposed: rewrite?.proposed ?? null, error: aiErrorMessage(error) }),
  });

  const errors = attempted ? offerFormErrors(form, true) : {};
  const stepIndex = WIZARD_STEPS.findIndex((item) => item.id === step);

  const updateForm = (next: OfferFormValues) => {
    if (next.image_url !== form.image_url) setImageFromWebsite(false);
    setAiMarked((current) => {
      const updated = { ...current };
      (Object.keys(next) as (keyof OfferFormValues)[]).forEach((key) => {
        if (next[key] !== form[key]) delete updated[key];
      });
      return updated;
    });
    setForm(next);
  };

  const set = <K extends keyof OfferFormValues>(key: K, value: OfferFormValues[K]) => updateForm({ ...form, [key]: value });

  const rewriteSlot = (field: AiRewriteField) => (
    <AiRewriteControl
      pending={rewriteField.isPending && rewrite?.field === field}
      error={rewrite?.field === field ? rewrite.error : null}
      proposed={rewrite?.field === field ? rewrite.proposed : null}
      onGenerate={(request) => {
        setRewrite({ field, proposed: null, error: null });
        rewriteField.mutate({ field, request });
      }}
      onAccept={() => {
        if (!rewrite?.proposed || rewrite.field !== field) return;
        updateForm({ ...form, [field]: rewrite.proposed });
        setRewrite(null);
      }}
      onCancel={() => setRewrite(null)}
    />
  );

  const goNext = () => {
    setAttempted(true);
    if (step === 'product' && (!form.name.trim() || !form.description.trim() || !form.category.trim())) return;
    if (step === 'reward') {
      const rewardErrors = offerFormErrors(form, true);
      if (rewardErrors.commission_value || !form.conversion_type) return;
    }
    if (step === 'promotion' && (!form.geo.trim() || form.allowed_traffic.length === 0)) return;
    const next = WIZARD_STEPS[stepIndex + 1];
    if (next) setStep(next.id);
  };

  const goPrev = () => {
    const prev = WIZARD_STEPS[stepIndex - 1];
    if (prev) setStep(prev.id);
  };

  if (phase === 'ai-brief') {
    return (
      <AiDraftBrief
        pending={generateDraft.isPending}
        error={briefError}
        onSubmit={(payload) => generateDraft.mutate(payload)}
        onCancel={onBack}
      />
    );
  }

  return (
    <div className="space-y-4 max-w-6xl">
      <button type="button" onClick={onBack} className="text-sm text-muted-foreground hover:text-primary">
        ← Офферы
      </button>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <h1 className="ui-page-title">Новый оффер</h1>
          <WizardStepper steps={[...WIZARD_STEPS]} current={step} onStep={(id) => setStep(id as WizardStepId)} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              if (form.name.trim() || form.description.trim()) fillMissing.mutate();
              else setPhase('ai-brief');
            }}
          >
            <Sparkles size={14} />
            {form.name.trim() || form.description.trim() ? 'Заполнить пропущенное' : 'AI-черновик'}
          </Button>
          <Button type="button" variant="secondary" disabled={createOffer.isPending} onClick={() => createOffer.mutate('draft')}>
            Сохранить как черновик
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,320px)]">
        <div className="ui-card p-5 space-y-5 min-w-0">
          {step === 'product' && (
            <>
              <SectionTitle title="Что вы хотите продвигать?" />
              <FieldShell label="Название оффера" required error={errors.name} extra={rewriteSlot('name')}>
                <input className={inputCls(errors.name)} value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Например, CRM Pro" />
                {aiMarked.name && <AiBadge />}
              </FieldShell>
              <FieldShell label="Категория" required>
                <SearchableCombobox value={form.category} options={[...CATEGORIES]} onChange={(v) => set('category', v)} />
                {aiMarked.category && <AiBadge />}
              </FieldShell>
              <FieldShell label="Сайт продукта" hint="Это не tracking-ссылка. Destination URL задаётся при создании ссылки.">
                {sites && sites.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    {sites.map((site) => (
                      <button
                        key={site.id}
                        type="button"
                        className="px-2 py-1 rounded-md text-xs border border-border hover:border-primary/40"
                        onClick={() => set('product_url', `https://${site.domain}`)}
                      >
                        {site.domain}
                      </button>
                    ))}
                  </div>
                )}
                <input className="ui-input" placeholder="https://" value={form.product_url} onChange={(e) => set('product_url', e.target.value)} />
              </FieldShell>
              <FieldShell
                label="Описание"
                required
                error={errors.description}
                extra={
                  <span className="flex items-center gap-2">
                    {rewriteSlot('description')}
                    <span className="text-xs text-muted-foreground tabular-nums">{form.description.length}/{DESCRIPTION_MAX}</span>
                  </span>
                }
              >
                <textarea
                  className={cn(inputCls(errors.description), 'min-h-[120px] resize-y')}
                  value={form.description}
                  onChange={(e) => set('description', e.target.value.slice(0, DESCRIPTION_MAX))}
                  placeholder="Коротко опишите продукт для партнёров"
                />
              </FieldShell>
              <FieldShell label="Изображение оффера">
                <div className="flex items-center gap-3 rounded-xl border border-dashed border-border p-3">
                  <OfferImage src={form.image_url} name={form.name || 'Оффер'} size="md" />
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <Button type="button" size="sm" variant="secondary" onClick={() => imageRef.current?.click()}>
                        <Upload size={14} />
                        {form.image_url ? 'Заменить' : 'Загрузить'}
                      </Button>
                      {form.image_url && (
                        <Button type="button" size="sm" variant="ghost" onClick={() => set('image_url', null)}>
                          <X size={14} />
                        </Button>
                      )}
                    </div>
                    {imageFromWebsite && form.image_url && <OfferAiFieldBadge variant="website" />}
                  </div>
                </div>
                <input ref={imageRef} type="file" accept="image/*" className="hidden" onChange={handleImageUpload(set, addToast)} />
              </FieldShell>
            </>
          )}

          {step === 'reward' && (
            <>
              <SectionTitle title="Вознаграждение партнёра" />
              <FieldShell label="За какое действие получает вознаграждение партнёр?" required>
                <div className="grid sm:grid-cols-2 gap-2">
                  {CONVERSION_GOAL_CARDS.map((card) => (
                    <SelectableCard
                      key={card.value}
                      selected={form.conversion_type === card.value}
                      title={card.title}
                      description={card.description}
                      badge={aiMarked.conversion_type ? 'AI' : undefined}
                      onClick={() => set('conversion_type', card.value)}
                    />
                  ))}
                </div>
              </FieldShell>
              <FieldShell label="Как рассчитывать вознаграждение?">
                <SegmentedControl
                  value={form.commission_type}
                  options={[
                    { value: 'percent', label: 'Процент от продажи' },
                    { value: 'fixed', label: 'Фиксированная сумма' },
                  ]}
                  onChange={(v) => set('commission_type', v)}
                />
              </FieldShell>
              <FieldShell
                label="Партнёр получает"
                required
                error={errors.commission_value}
                hint={commissionExample(form) || 'Укажите размер вознаграждения'}
              >
                <div className="flex items-center gap-2 max-w-xs">
                  <input
                    type="number"
                    min={0}
                    max={form.commission_type === 'percent' ? 100 : undefined}
                    step={form.commission_type === 'percent' ? 0.1 : 1}
                    className={inputCls(errors.commission_value)}
                    value={form.commission_value}
                    onChange={(e) => set('commission_value', e.target.value)}
                  />
                  {form.commission_type === 'percent' ? (
                    <span className="text-sm font-medium text-muted-foreground">%</span>
                  ) : (
                    <select className="ui-input w-24" value={form.commission_currency} onChange={(e) => set('commission_currency', e.target.value)}>
                      <option value="RUB">RUB</option>
                      <option value="USD">USD</option>
                      <option value="EUR">EUR</option>
                    </select>
                  )}
                </div>
                {form.commission_type === 'percent' && (
                  <p className="text-xs text-muted-foreground mt-1">Допустимый диапазон: от 0.1% до 100%</p>
                )}
              </FieldShell>
              <FieldShell
                label="Как долго закреплять клиента за партнёром?"
                hint="Если клиент перейдёт по ссылке партнёра и совершит целевое действие в течение этого периода, конверсия может быть закреплена за партнёром."
              >
                <ChipSelect
                  value={form.attribution_window_days}
                  options={ATTRIBUTION_PRESETS.map((days) => ({ value: String(days), label: `${days} дней` }))}
                  onChange={(v) => set('attribution_window_days', v)}
                  allowCustom
                  customValue={form.attribution_window_days}
                  onCustomChange={(v) => set('attribution_window_days', v)}
                />
              </FieldShell>
            </>
          )}

          {step === 'promotion' && (
            <>
              <SectionTitle title="Условия продвижения" />
              <FieldShell label="GEO" required>
                <GeoCombobox value={form.geo} options={[...GEO_OPTIONS]} onChange={(v) => set('geo', v)} />
              </FieldShell>
              <FieldShell label="Тип доступа">
                <div className="grid sm:grid-cols-3 gap-2">
                  {ACCESS_CARDS.map((card) => (
                    <SelectableCard
                      key={card.value}
                      selected={form.access_policy === card.value}
                      title={card.title}
                      description={card.description}
                      onClick={() => set('access_policy', card.value)}
                    />
                  ))}
                </div>
              </FieldShell>
              <FieldShell label="Где партнёры могут продвигать продукт?" required>
                <div className="grid sm:grid-cols-2 gap-2">
                  {TRAFFIC_SOURCE_CARDS.map((card) => {
                    const checked = card.keys.every((key) => form.allowed_traffic.includes(key));
                    return (
                      <CheckboxCard
                        key={card.label}
                        checked={checked}
                        label={card.label}
                        aiRecommended={aiMarked.allowed_traffic === 'generated' && checked}
                        onChange={() => {
                          const next = new Set(form.allowed_traffic);
                          if (checked) card.keys.forEach((key) => next.delete(key));
                          else card.keys.forEach((key) => next.add(key));
                          set('allowed_traffic', [...next]);
                        }}
                      />
                    );
                  })}
                </div>
              </FieldShell>
              <FieldShell label="Ограничения">
                <div className="space-y-2">
                  {RESTRICTION_PRESETS.map((preset) => (
                    <CheckboxCard
                      key={preset.id}
                      checked={form.selected_restrictions.includes(preset.id)}
                      label={preset.label}
                      onChange={() => toggleRestriction(form, updateForm, preset.id)}
                    />
                  ))}
                </div>
                <button
                  type="button"
                  className="text-sm text-primary hover:underline mt-2"
                  onClick={() => setAdvancedOpen(true)}
                >
                  + Добавить своё правило
                </button>
                {(advancedOpen || form.restrictions_custom) && (
                  <textarea
                    className="ui-input mt-2 min-h-[72px]"
                    placeholder="Своё правило для партнёров"
                    value={form.restrictions_custom}
                    onChange={(e) => set('restrictions_custom', e.target.value)}
                  />
                )}
              </FieldShell>
              <CollapsibleAdvanced form={form} open={advancedOpen} onToggle={() => setAdvancedOpen((v) => !v)} set={set} rewriteSlot={rewriteSlot} />
            </>
          )}

          {step === 'review' && (
            <>
              <SectionTitle title="Проверка и публикация" />
              <p className="text-sm text-muted-foreground">Проверьте, как оффер будет выглядеть для партнёров, и опубликуйте или сохраните черновик.</p>
              <OfferWizardPreview form={form} />
            </>
          )}

          <div className="flex justify-between gap-2 pt-2 border-t border-border/70">
            <Button type="button" variant="ghost" disabled={stepIndex === 0} onClick={goPrev}>
              Назад
            </Button>
            {step !== 'review' ? (
              <Button type="button" onClick={goNext}>
                Далее
              </Button>
            ) : (
              <Button
                type="button"
                disabled={createOffer.isPending || !canPublishOffer(form)}
                onClick={() => {
                  setAttempted(true);
                  if (canPublishOffer(form)) createOffer.mutate('active');
                }}
              >
                {createOffer.isPending ? 'Публикация...' : 'Опубликовать оффер'}
              </Button>
            )}
          </div>
        </div>

        <aside className="space-y-3 lg:sticky lg:top-4">
          <OfferWizardPreview form={form} />
          <OfferWizardReadiness form={form} onFillMissing={() => fillMissing.mutate()} fillPending={fillMissing.isPending} />
        </aside>
      </div>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h2 className="text-lg font-semibold">{title}</h2>;
}

function AiBadge() {
  return <OfferAiFieldBadge variant="recommendation" />;
}

function inputCls(error?: string) {
  return cn('ui-input', error && 'border-destructive');
}

function toggleRestriction(
  form: OfferFormValues,
  updateForm: (next: OfferFormValues) => void,
  id: string,
) {
  const preset = RESTRICTION_PRESETS.find((item) => item.id === id);
  if (!preset) return;
  const selected = form.selected_restrictions.includes(id);
  const nextSelected = selected ? form.selected_restrictions.filter((item) => item !== id) : [...form.selected_restrictions, id];
  let forbidden = [...form.forbidden_traffic];
  let restrictionsCustom = form.restrictions_custom;
  if ('traffic' in preset && preset.traffic) {
    if (selected) forbidden = forbidden.filter((item) => !(preset.traffic as readonly string[]).includes(item));
    else (preset.traffic as readonly string[]).forEach((item) => {
      if (!forbidden.includes(item)) forbidden.push(item);
    });
  } else if ('note' in preset && preset.note) {
    if (!selected && !restrictionsCustom.includes(preset.note)) {
      restrictionsCustom = restrictionsCustom ? `${restrictionsCustom}\n${preset.note}` : preset.note;
    }
  }
  updateForm({ ...form, selected_restrictions: nextSelected, forbidden_traffic: forbidden, restrictions_custom: restrictionsCustom });
}

function handleImageUpload(
  set: <K extends keyof OfferFormValues>(key: K, value: OfferFormValues[K]) => void,
  addToast: (msg: string, type: 'error' | 'success' | 'info') => void,
) {
  return async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      addToast('Файл больше 2 МБ', 'error');
      return;
    }
    try {
      set('image_url', await resizeImage(file, 240));
    } catch {
      addToast('Не удалось прочитать изображение', 'error');
    }
  };
}

function CollapsibleAdvanced({
  form,
  open,
  onToggle,
  set,
  rewriteSlot,
}: {
  form: OfferFormValues;
  open: boolean;
  onToggle: () => void;
  set: <K extends keyof OfferFormValues>(key: K, value: OfferFormValues[K]) => void;
  rewriteSlot: (field: AiRewriteField) => ReactNode;
}) {
  return (
    <div className="border border-border/70 rounded-xl">
      <button type="button" className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium" onClick={onToggle}>
        Расширенные настройки
        <ChevronDown size={16} className={cn('transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-border/70 pt-3">
          <FieldShell label="Комментарий для партнёров" extra={rewriteSlot('partner_notes')}>
            <textarea
              className="ui-input min-h-[72px]"
              value={form.partner_notes}
              onChange={(e) => set('partner_notes', e.target.value)}
              placeholder="Дополнительные инструкции"
            />
          </FieldShell>
        </div>
      )}
    </div>
  );
}
