import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { useToast } from '@/shared/components/Toast';
import { OfferEditor } from '@/shared/offers/OfferEditor';
import { emptyOfferForm, formToPayload, type OfferFormValues } from '@/shared/offers/types';
import { AiDraftBrief } from '@/shared/ai/AiDraftBrief';
import { AiRewriteControl } from '@/shared/ai/AiRewriteControl';
import { aiErrorMessage } from '@/shared/ai/messages';
import { draftMarks, draftToForm } from '@/shared/ai/offerDraft';
import type { AiMarkedFields, AiRewriteField, OfferAiDraftResponse, OfferAiRewriteResponse } from '@/shared/ai/types';

export function BusinessOfferNew() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { addToast } = useToast();
  const [form, setForm] = useState(emptyOfferForm());
  const [aiMarked, setAiMarked] = useState<AiMarkedFields>({});
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [briefMode, setBriefMode] = useState(searchParams.get('ai') === '1');
  const [briefError, setBriefError] = useState<string | null>(null);
  const [rewrite, setRewrite] = useState<{ field: AiRewriteField; proposed: string | null; error: string | null } | null>(
    null,
  );
  const [imageFromWebsite, setImageFromWebsite] = useState(false);

  const createOffer = useMutation({
    mutationFn: (status: 'draft' | 'active') => api.post<{ id: string }>('/business/offers', formToPayload(form, status)),
    onSuccess: async (data) => {
      if (generationId) {
        await api
          .post(`/ai/generations/${generationId}/feedback`, {
            outcome: 'EDITED_AFTER_GENERATION',
          })
          .catch(() => undefined);
      }
      addToast('Оффер сохранён', 'success');
      navigate(`/business/offers/${data.id}`);
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
      setBriefMode(false);
      if (data.website?.status === 'unavailable') {
        addToast('Не удалось получить информацию со страницы. Черновик будет создан на основе вашего описания.', 'info');
      }
    },
    onError: (error) => setBriefError(aiErrorMessage(error, 'Не удалось создать черновик. Попробуйте ещё раз.')),
  });

  const rewriteField = useMutation({
    mutationFn: ({ field, instruction }: { field: AiRewriteField; instruction: string }) =>
      api.post<OfferAiRewriteResponse>(`/ai/offers/fields/${field}/rewrite`, {
        instruction,
        value: form[field],
        context: form,
      }),
    onSuccess: (data) => {
      setRewrite({ field: data.field as AiRewriteField, proposed: data.value, error: null });
    },
    onError: (error, variables) => {
      setRewrite({ field: variables.field, proposed: rewrite?.proposed ?? null, error: aiErrorMessage(error) });
    },
  });

  const goBack = () => navigate('/business/offers');

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

  if (briefMode) {
    return (
      <AiDraftBrief
        pending={generateDraft.isPending}
        error={briefError}
        onSubmit={(payload) => generateDraft.mutate(payload)}
        onCancel={goBack}
      />
    );
  }

  return (
    <OfferEditor
      title="Новый оффер"
      backLabel="← Офферы"
      onBack={goBack}
      form={form}
      onChange={updateForm}
      pending={createOffer.isPending}
      secondaryLabel="Сохранить как черновик"
      primaryLabel="Создать оффер"
      requireCommission
      onCancel={goBack}
      onSecondary={() => createOffer.mutate('draft')}
      onPrimary={() => createOffer.mutate('active')}
      aiMarked={aiMarked}
      imageFromWebsite={imageFromWebsite}
      rewriteSlot={(field) => (
        <AiRewriteControl
          pending={rewriteField.isPending && rewrite?.field === field}
          error={rewrite?.field === field ? rewrite.error : null}
          proposed={rewrite?.field === field ? rewrite.proposed : null}
          onGenerate={(instruction) => {
            setRewrite({ field, proposed: null, error: null });
            rewriteField.mutate({ field, instruction });
          }}
          onAccept={() => {
            if (!rewrite?.proposed || rewrite.field !== field) return;
            updateForm({ ...form, [field]: rewrite.proposed });
            setRewrite(null);
          }}
          onCancel={() => setRewrite(null)}
        />
      )}
    />
  );
}
