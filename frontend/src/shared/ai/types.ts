export type AiFieldKind = 'content' | 'recommendation';

export type OfferAiDraft = {
  name: string;
  description: string;
  category: string;
  geo: string;
  partner_notes: string;
  allowed_traffic: string[];
  forbidden_traffic: string[];
  product_url: string;
};

export type OfferAiRecommendations = {
  conversion_type: string;
  commission_type: string;
  commission_value: number;
  commission_currency: string;
  attribution_window_days: number;
  access_policy: string;
};

export type OfferAiDraftResponse = {
  generation_id: string;
  draft: OfferAiDraft;
  recommendations: OfferAiRecommendations;
  image_url?: string | null;
  website?: { status: 'ok' | 'unavailable' | 'skipped' };
};

export type OfferAiChange = {
  field: string;
  old_value: unknown;
  new_value: unknown;
  reason: string;
  kind: AiFieldKind;
};

export type OfferAiEditResponse = {
  generation_id: string;
  changes: OfferAiChange[];
};

export type OfferAiRewriteResponse = {
  generation_id: string;
  field: string;
  value: string;
};

export const AI_CONTENT_FIELDS = [
  'name',
  'description',
  'category',
  'geo',
  'partner_notes',
  'allowed_traffic',
  'forbidden_traffic',
  'product_url',
] as const;

export const AI_RECOMMENDED_FIELDS = [
  'conversion_type',
  'commission_type',
  'commission_value',
  'commission_currency',
  'attribution_window_days',
  'access_policy',
] as const;

export const AI_REWRITE_FIELDS = ['name', 'description', 'partner_notes'] as const;

export type AiRewriteField = (typeof AI_REWRITE_FIELDS)[number];
export type AiMarkedFields = Partial<Record<string, 'generated' | 'recommended' | 'applied'>>;
