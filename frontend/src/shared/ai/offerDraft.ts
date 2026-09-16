import { parseGeoCodes } from '@/shared/catalog/countries';
import { normalizeTrafficSource } from '@/shared/catalog/trafficSources';
import { resolveCategoryCode } from '@/shared/catalog/categories';
import { emptyOfferForm, type OfferFormValues } from '@/shared/offers/types';
import type { OfferAiDraft, OfferAiRecommendations } from '@/shared/ai/types';
import { AI_CONTENT_FIELDS, AI_RECOMMENDED_FIELDS, type AiMarkedFields } from '@/shared/ai/types';

export function mergeAiDraftIntoForm(
  form: OfferFormValues,
  draft: OfferAiDraft,
  recommendations: OfferAiRecommendations,
  imageUrl?: string | null,
  onlyMissing = false,
): OfferFormValues {
  const pickStr = (current: string, next: string) => (onlyMissing ? current.trim() || next : next || current);
  const nextGeo = parseGeoCodes(draft.geo);
  const nextTraffic = (draft.allowed_traffic || [])
    .map((item) => normalizeTrafficSource(item))
    .filter((item): item is string => Boolean(item));

  return {
    ...form,
    name: pickStr(form.name, draft.name),
    description: pickStr(form.description, draft.description),
    category: pickStr(form.category, resolveCategoryCode(draft.category) || ''),
    geo_countries: onlyMissing && form.geo_countries.length > 0 ? form.geo_countries : nextGeo.length ? nextGeo : form.geo_countries,
    partner_notes: pickStr(form.partner_notes, draft.partner_notes || ''),
    allowed_traffic: onlyMissing && form.allowed_traffic.length > 0 ? form.allowed_traffic : nextTraffic.length ? nextTraffic : form.allowed_traffic,
    product_url: pickStr(form.product_url, draft.product_url || ''),
    image_url: onlyMissing ? form.image_url || imageUrl || null : imageUrl || form.image_url,
    conversion_type: pickStr(form.conversion_type, recommendations.conversion_type),
    commission_type: pickStr(form.commission_type, recommendations.commission_type),
    commission_value: onlyMissing && Number(form.commission_value) > 0 ? form.commission_value : String(recommendations.commission_value),
    commission_currency: pickStr(form.commission_currency, recommendations.commission_currency),
    attribution_window_days:
      onlyMissing && Number(form.attribution_window_days) > 0
        ? form.attribution_window_days
        : String(recommendations.attribution_window_days),
    access_policy: pickStr(form.access_policy, recommendations.access_policy),
  };
}

export function draftToForm(
  draft: OfferAiDraft,
  recommendations: OfferAiRecommendations,
  imageUrl?: string | null,
): OfferFormValues {
  return mergeAiDraftIntoForm(emptyOfferForm(), draft, recommendations, imageUrl, false);
}

export function draftMarks(): AiMarkedFields {
  const marks: AiMarkedFields = {};
  for (const field of AI_CONTENT_FIELDS) marks[field] = 'generated';
  for (const field of AI_RECOMMENDED_FIELDS) marks[field] = 'recommended';
  return marks;
}

export function applyFormValue(form: OfferFormValues, field: string, value: unknown): OfferFormValues {
  if (field === 'commission_value' || field === 'attribution_window_days' || field === 'hold_period_days') {
    return { ...form, [field]: String(value ?? '') };
  }
  if (field === 'allowed_traffic' || field === 'geo_countries') {
    return { ...form, [field]: Array.isArray(value) ? value.map(String) : [] };
  }
  if (field === 'geo') {
    return { ...form, geo_countries: parseGeoCodes(typeof value === 'string' ? value : Array.isArray(value) ? value.map(String) : []) };
  }
  if (field === 'category') {
    return { ...form, category: resolveCategoryCode(String(value ?? '')) || '' };
  }
  return { ...form, [field]: value == null ? '' : String(value) } as OfferFormValues;
}

export function formValue(form: OfferFormValues, field: string): unknown {
  if (field === 'geo') return form.geo_countries.join(',');
  return form[field as keyof OfferFormValues];
}
