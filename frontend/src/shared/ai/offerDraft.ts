import { emptyOfferForm, type OfferFormValues } from '@/shared/offers/types';
import type { OfferAiDraft, OfferAiRecommendations } from '@/shared/ai/types';
import { AI_CONTENT_FIELDS, AI_RECOMMENDED_FIELDS, type AiMarkedFields } from '@/shared/ai/types';

export function draftToForm(
  draft: OfferAiDraft,
  recommendations: OfferAiRecommendations,
  imageUrl?: string | null,
): OfferFormValues {
  return {
    ...emptyOfferForm(),
    name: draft.name,
    description: draft.description,
    category: draft.category,
    geo: draft.geo,
    partner_notes: draft.partner_notes || '',
    allowed_traffic: draft.allowed_traffic || [],
    forbidden_traffic: draft.forbidden_traffic || [],
    product_url: draft.product_url || '',
    image_url: imageUrl || null,
    conversion_type: recommendations.conversion_type,
    commission_type: recommendations.commission_type,
    commission_value: String(recommendations.commission_value),
    commission_currency: recommendations.commission_currency,
    attribution_window_days: String(recommendations.attribution_window_days),
    access_policy: recommendations.access_policy,
  };
}

export function draftMarks(): AiMarkedFields {
  const marks: AiMarkedFields = {};
  for (const field of AI_CONTENT_FIELDS) marks[field] = 'generated';
  for (const field of AI_RECOMMENDED_FIELDS) marks[field] = 'recommended';
  return marks;
}

export function applyFormValue(form: OfferFormValues, field: string, value: unknown): OfferFormValues {
  if (field === 'commission_value' || field === 'attribution_window_days') {
    return { ...form, [field]: String(value ?? '') };
  }
  if (field === 'allowed_traffic' || field === 'forbidden_traffic') {
    return { ...form, [field]: Array.isArray(value) ? value.map(String) : [] };
  }
  return { ...form, [field]: value == null ? '' : String(value) } as OfferFormValues;
}

export function formValue(form: OfferFormValues, field: string): unknown {
  return form[field as keyof OfferFormValues];
}
