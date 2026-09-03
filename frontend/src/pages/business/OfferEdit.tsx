import { useEffect, useReducer, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { OfferEditor } from '@/shared/offers/OfferEditor';
import { emptyOfferForm, formToPayload, type OfferFormValues } from '@/shared/offers/types';
import { OfferAiEditPanel } from '@/shared/ai/OfferAiEditPanel';
import { AiRewriteControl } from '@/shared/ai/AiRewriteControl';
import { aiErrorMessage } from '@/shared/ai/messages';
import {
  canRequestOfferAiEdit,
  createOfferAiEditState,
  offerAiEditReducer,
  selectedSuggestions,
} from '@/shared/ai/offerEditSession';
import { applyFormValue } from '@/shared/ai/offerDraft';
import { toAiGuidancePayload, type AiGuidanceRequest } from '@/shared/ai/presets';
import type {
  AiMarkedFields,
  AiRewriteField,
  OfferAiEditResponse,
  OfferAiRewriteResponse,
} from '@/shared/ai/types';

interface OfferDetail {
  name: string;
  description: string | null;
  image_url?: string | null;
  category?: string | null;
  geo?: string | null;
  conversion_type: string;
  access_policy: string;
  attribution_window_days: number;
  partner_notes?: string | null;
  allowed_traffic?: string[];
  forbidden_traffic?: string[];
  product_url?: string | null;
  commission_rules: Array<{ type: string; value: number; currency: string | null }>;
  status: string;
}

export function BusinessOfferEdit() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [form, setForm] = useState<OfferFormValues>(emptyOfferForm());
  const [aiMarked, setAiMarked] = useState<AiMarkedFields>({});
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [session, dispatch] = useReducer(
    offerAiEditReducer,
    searchParams.get('ai') === '1',
    (open) => createOfferAiEditState(open),
  );
  const [rewrite, setRewrite] = useState<{ field: AiRewriteField; proposed: string | null; error: string | null } | null>(
    null,
  );
  const aiRequestInFlight = useRef(false);

  const { data, isLoading } = useQuery<OfferDetail>({
    queryKey: ['business', 'offers', id],
    queryFn: () => api.get(`/business/offers/${id}`),
    enabled: !!id,
  });

  useEffect(() => {
    if (!data) return;
    const rule = data.commission_rules?.[0];
    setForm({
      name: data.name,
      category: data.category || 'SaaS',
      image_url: data.image_url || null,
      description: data.description || '',
      conversion_type: data.conversion_type,
      commission_type: rule?.type || 'percent',
      commission_value: String(rule?.value ?? 10),
      commission_currency: rule?.currency || 'RUB',
      attribution_window_days: String(data.attribution_window_days || 30),
      access_policy: data.access_policy,
      geo: data.geo || 'RU',
      allowed_traffic: data.allowed_traffic || [],
      forbidden_traffic: data.forbidden_traffic || [],
      partner_notes: data.partner_notes || '',
      product_url: data.product_url || '',
      restrictions_custom: '',
      selected_restrictions: [],
    });
  }, [data]);

  const save = useMutation({
    mutationFn: (status?: string) =>
      api.patch(`/business/offers/${id}`, {
        ...formToPayload(form, (status as 'draft' | 'active') || (data?.status as 'draft' | 'active') || 'draft'),
        status: status || data?.status,
      }),
    onSuccess: async () => {
      if (generationId) {
        await api
          .post(`/ai/generations/${generationId}/feedback`, { outcome: 'EDITED_AFTER_GENERATION' })
          .catch(() => undefined);
      }
      addToast('Изменения сохранены', 'success');
      navigate(`/business/offers/${id}`);
    },
    onError: () => addToast('Не удалось сохранить оффер', 'error'),
  });

  const editWithAi = useMutation({
    mutationFn: (request: AiGuidanceRequest) =>
      api.post<OfferAiEditResponse>(`/ai/offers/${id}/edit`, { ...toAiGuidancePayload(request), context: form }),
    onSuccess: (payload) => {
      setGenerationId(payload.generation_id);
      dispatch({ type: 'SUCCESS', changes: payload.changes });
    },
    onError: () => dispatch({ type: 'FAIL', error: 'Не удалось получить предложения.' }),
  });

  const rewriteField = useMutation({
    mutationFn: ({ field, request }: { field: AiRewriteField; request: AiGuidanceRequest }) =>
      api.post<OfferAiRewriteResponse>(`/ai/offers/${id}/fields/${field}/rewrite`, {
        ...toAiGuidancePayload(request),
        value: form[field],
        context: form,
      }),
    onSuccess: (payload) => {
      setRewrite({ field: payload.field as AiRewriteField, proposed: payload.value, error: null });
    },
    onError: (error, variables) => {
      setRewrite({ field: variables.field, proposed: rewrite?.proposed ?? null, error: aiErrorMessage(error) });
    },
  });

  if (isLoading || !data) {
    return <Skeleton className="h-96 rounded-xl" />;
  }

  const goBack = () => navigate(`/business/offers/${id}`);

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

  const requestSuggestions = () => {
    if (!canRequestOfferAiEdit(session) || aiRequestInFlight.current) return;
    aiRequestInFlight.current = true;
    dispatch({ type: 'REQUEST' });
    editWithAi.mutate(
      { preset: session.preset ?? undefined, guidance: session.instruction.trim() || undefined },
      {
      onSettled: () => {
        aiRequestInFlight.current = false;
      },
    });
  };

  const applySelected = () => {
    const chosen = selectedSuggestions(session);
    if (chosen.length === 0) return;
    setForm((current) =>
      chosen.reduce((next, change) => applyFormValue(next, change.field, change.new_value), current),
    );
    setAiMarked((current) => {
      const updated = { ...current };
      chosen.forEach((change) => {
        updated[change.field] = 'applied';
      });
      return updated;
    });
    dispatch({ type: 'APPLIED', count: chosen.length });
  };

  return (
    <>
      <OfferEditor
        title="Редактирование оффера"
        backLabel="← К офферу"
        onBack={goBack}
        form={form}
        onChange={updateForm}
        status={data.status}
        financialWarning={searchParams.get('focus') === 'terms'}
        pending={save.isPending}
        secondaryLabel="Сохранить изменения"
        primaryLabel="Обновить оффер"
        requireCommission={false}
        onCancel={goBack}
        onSecondary={() => save.mutate(data.status)}
        onPrimary={() => save.mutate(data.status === 'draft' ? 'active' : data.status)}
        aiMarked={aiMarked}
        tools={
          session.phase === 'closed' ? (
            <Button type="button" variant="outline" onClick={() => dispatch({ type: 'OPEN' })}>
              <Sparkles size={16} />
              Изменить с AI
            </Button>
          ) : undefined
        }
        banner={
          session.phase === 'closed' ? undefined : (
            <OfferAiEditPanel
              state={session}
              dispatch={dispatch}
              onRequest={requestSuggestions}
              onApply={applySelected}
            />
          )
        }
        rewriteSlot={(field) => (
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
        )}
      />
      {session.confirmClose && (
        <ConfirmDialog
          title="Закрыть AI-редактирование?"
          confirmLabel="Закрыть"
          cancelLabel="Остаться"
          onClose={() => dispatch({ type: 'STAY' })}
          onConfirm={() => dispatch({ type: 'CLOSE' })}
        >
          <p>Неприменённые предложения будут удалены.</p>
          <p>Изменения, уже применённые к форме, сохранятся.</p>
        </ConfirmDialog>
      )}
    </>
  );
}
