import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { AiDraftBrief } from '@/shared/ai/AiDraftBrief';
import { AiRewriteControl } from '@/shared/ai/AiRewriteControl';
import { aiErrorMessage } from '@/shared/ai/messages';
import { toAiRewritePayload, type AiRewriteRequest } from '@/shared/ai/presets';
import { draftMarks, draftToForm } from '@/shared/ai/offerDraft';
import type { AiMarkedFields, AiRewriteField, OfferAiDraftResponse, OfferAiRewriteResponse } from '@/shared/ai/types';
import { searchTrafficSources } from '@/shared/catalog/trafficSources';
import { DESCRIPTION_MAX, PARTNER_NOTES_MAX, stepErrors } from '@/shared/offers/offerFormMeta';
import { blankOfferForm, formToPayload, type OfferFormValues } from '@/shared/offers/types';
import {
  ACCESS_CARDS,
  ATTRIBUTION_PRESETS,
  CONVERSION_GOAL_CARDS,
  HOLD_PRESETS,
  WIZARD_STEPS,
  commissionExample,
  daysLabel,
  holdHelper,
  type WizardStepId,
} from '@/shared/offers/wizard/meta';
import { OfferImageField } from '@/shared/offers/wizard/OfferImageField';
import {
  OfferWizardFormCard,
  OfferWizardGrid,
  OfferWizardHeader,
  OfferWizardWorkspace,
} from '@/shared/offers/wizard/OfferWizardLayout';
import { OfferReviewPreview, OfferWizardPreview, OfferWizardReadiness } from '@/shared/offers/wizard/OfferWizardPanels';
import { canPublishOffer, stepComplete } from '@/shared/offers/wizard/readiness';
import {
  CategoryCombobox,
  CheckboxCard,
  ChipSelect,
  CountryMultiSelect,
  FieldShell,
  SegmentedControl,
  SelectableCard,
  SiteCombobox,
  WizardStepper,
} from '@/shared/offers/wizard/ui';
import type { BusinessSite } from '@/pages/business/settings/types';
import { cn } from '@/shared/utils/cn';

type Phase = 'ai-brief' | 'wizard';

export function OfferWizard({
  mode = 'create',
  initialAiBrief = false,
  initialForm,
  offerId,
  status,
  onBack,
  onSaved,
}: {
  mode?: 'create' | 'edit';
  initialAiBrief?: boolean;
  initialForm?: OfferFormValues;
  offerId?: string;
  status?: string;
  onBack: () => void;
  onSaved: (id: string) => void;
}) {
  const { addToast } = useToast();
  const [phase, setPhase] = useState<Phase>(() => (initialAiBrief ? 'ai-brief' : 'wizard'));
  const [step, setStep] = useState<WizardStepId>('basics');
  const [form, setForm] = useState<OfferFormValues>(() => initialForm || blankOfferForm());
  const [aiMarked, setAiMarked] = useState<AiMarkedFields>({});
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [attempted, setAttempted] = useState(false);
  const [rewrite, setRewrite] = useState<{ field: AiRewriteField; proposed: string | null; error: string | null } | null>(null);
  const [trafficQuery, setTrafficQuery] = useState('');

  const { data: sites } = useQuery<BusinessSite[]>({
    queryKey: ['business', 'sites'],
    queryFn: () => api.get('/business/sites'),
  });

  const createOffer = useMutation({
    mutationFn: (nextStatus: 'draft' | 'active') => api.post<{ id: string }>('/business/offers', formToPayload(form, nextStatus)),
    onSuccess: async (data, nextStatus) => {
      if (generationId) {
        await api.post(`/ai/generations/${generationId}/feedback`, { outcome: 'EDITED_AFTER_GENERATION' }).catch(() => undefined);
      }
      addToast(nextStatus === 'active' ? 'Оффер опубликован' : 'Черновик сохранён', 'success');
      onSaved(data.id);
    },
    onError: () => addToast('Не удалось сохранить оффер', 'error'),
  });

  const updateOffer = useMutation({
    mutationFn: (nextStatus?: string) =>
      api.patch(`/business/offers/${offerId}`, {
        ...formToPayload(form, nextStatus || status || 'draft'),
        status: nextStatus || status,
      }),
    onSuccess: async () => {
      if (generationId) {
        await api.post(`/ai/generations/${generationId}/feedback`, { outcome: 'EDITED_AFTER_GENERATION' }).catch(() => undefined);
      }
      addToast('Изменения сохранены', 'success');
      onSaved(String(offerId));
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
      setBriefError(null);
      setPhase('wizard');
      setStep('basics');
    },
    onError: (error) => setBriefError(aiErrorMessage(error)),
  });

  const rewriteField = useMutation({
    mutationFn: ({ field, request }: { field: AiRewriteField; request: AiRewriteRequest }) =>
      api.post<OfferAiRewriteResponse>(
        offerId ? `/ai/offers/${offerId}/fields/${field}/rewrite` : `/ai/offers/fields/${field}/rewrite`,
        { ...toAiRewritePayload(request), value: form[field], context: form },
      ),
    onSuccess: (data) => setRewrite({ field: data.field as AiRewriteField, proposed: data.value, error: null }),
    onError: (error, variables) =>
      setRewrite({ field: variables.field, proposed: rewrite?.proposed ?? null, error: aiErrorMessage(error) }),
  });

  const errors = attempted ? stepErrors(form, step === 'review' ? 'conversions' : step) : {};
  const stepIndex = WIZARD_STEPS.findIndex((item) => item.id === step);
  const reachable = WIZARD_STEPS.filter((_item, index) => {
    if (index === 0) return true;
    const prev = WIZARD_STEPS[index - 1];
    return prev.id === 'review' || stepComplete(form, prev.id as 'basics' | 'traffic' | 'conversions') || index <= stepIndex;
  }).map((item) => item.id as string);
  const pending = createOffer.isPending || updateOffer.isPending;
  const isActive = status === 'active';

  const updateForm = (next: OfferFormValues) => {
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

  const rewriteSlot = (field: AiRewriteField, label: string) => (
    <AiRewriteControl
      label={label}
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
    if (step !== 'review' && !stepComplete(form, step)) return;
    const next = WIZARD_STEPS[stepIndex + 1];
    if (next) {
      setAttempted(false);
      setStep(next.id);
    }
  };

  const goPrev = () => {
    const prev = WIZARD_STEPS[stepIndex - 1];
    if (prev) {
      setAttempted(false);
      setStep(prev.id);
    }
  };

  const save = (nextStatus?: 'draft' | 'active') => {
    if (mode === 'edit') {
      updateOffer.mutate(nextStatus || status);
      return;
    }
    createOffer.mutate(nextStatus || 'draft');
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

  const trafficSources = searchTrafficSources(trafficQuery);

  return (
    <OfferWizardWorkspace>
      <OfferWizardHeader
        title={mode === 'edit' ? 'Редактирование оффера' : `Создание оффера — Шаг ${stepIndex + 1} из 4`}
        backLabel={mode === 'edit' ? '← К офферу' : '← К списку офферов'}
        onBack={onBack}
      />

      <OfferWizardGrid
        stepper={
          <WizardStepper
            steps={[...WIZARD_STEPS]}
            current={step}
            reachable={reachable}
            onStep={(id) => {
              if (reachable.includes(id)) {
                setAttempted(false);
                setStep(id as WizardStepId);
              }
            }}
          />
        }
        aside={
          step !== 'review' ? (
            <>
              <OfferWizardPreview form={form} />
              <OfferWizardReadiness form={form} current={step} />
            </>
          ) : (
            <OfferWizardReadiness form={form} current={step} />
          )
        }
        main={
          <OfferWizardFormCard>
          {step === 'basics' && (
            <>
              <div>
                <h2 className="text-lg font-semibold">Основная информация</h2>
              </div>
              <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,1fr)]">
                <FieldShell label="Название оффера" required error={errors.name} extra={rewriteSlot('name', 'Улучшить')}>
                  <input className={inputCls(errors.name)} value={form.name} onChange={(e) => set('name', e.target.value)} />
                </FieldShell>
                <FieldShell label="Категория" required error={errors.category}>
                  <CategoryCombobox value={form.category} onChange={(value) => set('category', value)} error={Boolean(errors.category)} />
                </FieldShell>
                <FieldShell label="Сайт продукта">
                  <SiteCombobox value={form.product_url} onChange={(value) => set('product_url', value)} sites={sites} />
                </FieldShell>
              </div>
              <div className="grid grid-cols-1 items-stretch gap-4 lg:[grid-template-columns:minmax(160px,min(32%,200px))_minmax(0,1fr)]">
                <FieldShell label="Изображение">
                  <OfferImageField
                    src={form.image_url}
                    onChange={(value) => set('image_url', value)}
                    onError={(message) => addToast(message, 'error')}
                  />
                </FieldShell>
                <FieldShell
                  label="Описание оффера"
                  required
                  fill
                  hint="Это описание поможет партнёру понять продукт и оценить оффер."
                  error={errors.description}
                  extra={
                    <span className="flex items-center gap-2">
                      {rewriteSlot('description', 'Сформировать')}
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {form.description.length}/{DESCRIPTION_MAX}
                      </span>
                    </span>
                  }
                >
                  <textarea
                    className={cn(inputCls(errors.description), 'min-h-[140px] resize-none lg:min-h-0 lg:flex-1 lg:h-full')}
                    value={form.description}
                    onChange={(e) => set('description', e.target.value.slice(0, DESCRIPTION_MAX))}
                    placeholder="Опишите продукт или услугу, для кого они предназначены и в чём их основная ценность"
                  />
                </FieldShell>
              </div>
              <FieldShell
                label="Комментарий для партнёра"
                hint="Комментарий носит информационный характер. GEO, разрешённые источники трафика и условия вознаграждения задаются отдельными параметрами оффера."
                error={errors.partner_notes}
                extra={
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {form.partner_notes.length}/{PARTNER_NOTES_MAX}
                  </span>
                }
              >
                <textarea
                  rows={4}
                  className={cn(inputCls(errors.partner_notes), 'min-h-[88px] resize-y')}
                  value={form.partner_notes}
                  onChange={(e) => set('partner_notes', e.target.value.slice(0, PARTNER_NOTES_MAX))}
                  placeholder="Добавьте рекомендации партнёру: на какую аудиторию ориентироваться, какие преимущества подчёркивать и какие особенности продвижения учитывать"
                />
              </FieldShell>
              <FieldShell
                label="Доступ к офферу"
                required
                error={errors.access_policy}
                hint="Выберите, кто сможет видеть и продвигать этот оффер."
              >
                <div className="grid grid-cols-1 gap-2 md:grid-cols-[repeat(3,minmax(0,1fr))]">
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
            </>
          )}

          {step === 'traffic' && (
            <>
              <h2 className="text-lg font-semibold">Параметры трафика</h2>
              <div className="grid lg:grid-cols-2 gap-5">
                <FieldShell label="География" required error={errors.geo_countries}>
                  <CountryMultiSelect
                    value={form.geo_countries}
                    onChange={(value) => set('geo_countries', value)}
                    error={Boolean(errors.geo_countries)}
                  />
                </FieldShell>
                <FieldShell
                  label="Разрешённые источники трафика"
                  required
                  error={errors.allowed_traffic}
                  hint="Партнёры могут использовать только выбранные источники. Все остальные источники запрещены."
                >
                  <div className="relative mb-2">
                    <input
                      className="ui-input h-9"
                      placeholder="Поиск по источникам..."
                      value={trafficQuery}
                      onChange={(e) => setTrafficQuery(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2 max-h-[280px] overflow-auto pr-1">
                    {trafficSources.map((source) => {
                      const checked = form.allowed_traffic.includes(source.code);
                      return (
                        <CheckboxCard
                          key={source.code}
                          checked={checked}
                          label={source.nameRu}
                          onChange={() => {
                            set(
                              'allowed_traffic',
                              checked
                                ? form.allowed_traffic.filter((item) => item !== source.code)
                                : [...form.allowed_traffic, source.code],
                            );
                          }}
                        />
                      );
                    })}
                  </div>
                </FieldShell>
              </div>
            </>
          )}

          {step === 'conversions' && (
            <>
              <div>
                <h2 className="text-lg font-semibold">Настройте вознаграждение для партнёра</h2>
                <p className="text-sm text-muted-foreground mt-1">Укажите, за какое действие и сколько получает партнёр.</p>
              </div>
              <div className="grid lg:grid-cols-2 gap-5">
                <div className="space-y-4">
                  <FieldShell label="За какое действие получает вознаграждение партнёр?" required error={errors.conversion_type}>
                    <div className="grid grid-cols-2 gap-2">
                      {CONVERSION_GOAL_CARDS.map((card) => (
                        <SelectableCard
                          key={card.value}
                          selected={form.conversion_type === card.value}
                          title={card.title}
                          description={card.description}
                          onClick={() => set('conversion_type', card.value)}
                        />
                      ))}
                    </div>
                  </FieldShell>
                  <FieldShell label="Размер комиссии" required error={errors.commission_value} hint={commissionExample(form) || undefined}>
                    <div className="flex items-center gap-2 max-w-xs">
                      <div className="relative flex-1">
                        <input
                          type="number"
                          min={0}
                          max={form.commission_type === 'percent' ? 100 : undefined}
                          className={cn(inputCls(errors.commission_value), form.commission_type === 'percent' && 'pr-10')}
                          value={form.commission_value}
                          onChange={(e) => set('commission_value', e.target.value)}
                        />
                        {form.commission_type === 'percent' && (
                          <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted-foreground">%</span>
                        )}
                      </div>
                      {form.commission_type === 'fixed' && (
                        <select className="ui-input w-24" value={form.commission_currency} onChange={(e) => set('commission_currency', e.target.value)}>
                          <option value="RUB">RUB</option>
                          <option value="USD">USD</option>
                          <option value="EUR">EUR</option>
                        </select>
                      )}
                    </div>
                  </FieldShell>
                </div>
                <div className="space-y-4">
                  <FieldShell label="Как рассчитывается вознаграждение?" required>
                    <SegmentedControl
                      value={form.commission_type}
                      options={[
                        { value: 'percent', label: '% от продажи' },
                        { value: 'fixed', label: 'Фиксированная сумма' },
                      ]}
                      onChange={(value) => set('commission_type', value)}
                    />
                  </FieldShell>
                  <FieldShell
                    label="Как долго закреплять клиента за партнёром?"
                    required
                    hint="Если клиент совершит целевое действие в течение этого периода, конверсия будет закреплена за партнёром."
                  >
                    <ChipSelect
                      value={form.attribution_window_days}
                      options={ATTRIBUTION_PRESETS.map((days) => ({ value: String(days), label: daysLabel(days) }))}
                      onChange={(value) => set('attribution_window_days', value)}
                    />
                  </FieldShell>
                  <FieldShell
                    label="Холд-период"
                    required
                    hint={holdHelper(form.hold_period_days)}
                  >
                    <ChipSelect
                      value={form.hold_period_days}
                      options={HOLD_PRESETS.map((days) => ({ value: String(days), label: daysLabel(days) }))}
                      onChange={(value) => set('hold_period_days', value)}
                    />
                    {mode === 'edit' && isActive && (
                      <p className="text-xs text-muted-foreground mt-1.5">Новое значение применяется только к новым конверсиям.</p>
                    )}
                  </FieldShell>
                </div>
              </div>
            </>
          )}

          {step === 'review' && <OfferReviewPreview form={form} onEdit={setStep} />}

          <div className="flex items-center justify-between gap-2 border-t border-border/70 pt-3">
            {step === 'basics' ? (
              <Button type="button" variant="secondary" onClick={onBack}>
                Отмена
              </Button>
            ) : (
              <Button type="button" variant="secondary" onClick={goPrev}>
                {step === 'traffic' ? '← Назад' : step === 'conversions' ? '← Назад: Трафик' : '← Назад'}
              </Button>
            )}
            {step !== 'review' ? (
              <Button type="button" onClick={goNext}>
                {step === 'basics' ? 'Далее' : step === 'traffic' ? 'Далее: Конверсии →' : 'Далее: Проверка →'}
              </Button>
            ) : mode === 'create' ? (
              <div className="flex gap-2">
                <Button type="button" variant="secondary" disabled={pending} onClick={() => save('draft')}>
                  Сохранить как черновик
                </Button>
                <Button
                  type="button"
                  disabled={pending || !canPublishOffer(form)}
                  onClick={() => {
                    setAttempted(true);
                    if (canPublishOffer(form)) save('active');
                  }}
                >
                  {pending ? 'Публикация...' : 'Опубликовать оффер'}
                </Button>
              </div>
            ) : (
              <Button type="button" disabled={pending} onClick={() => save()}>
                {pending ? 'Сохранение...' : 'Сохранить изменения'}
              </Button>
            )}
          </div>
          </OfferWizardFormCard>
        }
      />
      {aiMarked.name ? <span className="sr-only">AI</span> : null}
    </OfferWizardWorkspace>
  );
}

function inputCls(error?: string) {
  return cn('ui-input', error && 'border-destructive');
}

