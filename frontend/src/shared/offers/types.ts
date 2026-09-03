export interface CommissionRule {
  id?: number | string;
  type: string;
  value: number;
  currency: string | null;
}

export interface OfferListItem {
  id: number | string;
  name: string;
  description: string | null;
  image_url?: string | null;
  category?: string | null;
  geo?: string | null;
  status: string;
  access_policy: string;
  conversion_type: string;
  partners_count?: number;
  clicks?: number;
  conversions?: number;
  cr?: number;
  epc?: number;
  partner_status?: string | null;
  promotion_status?: 'ACTIVE' | 'PAUSED' | 'NOT_STARTED' | null;
  active_links_count?: number;
  total_links_count?: number;
  partner_clicks?: number;
  partner_conversions?: number;
  partner_cr?: number;
  commission_rules: CommissionRule[];
  allowed_traffic?: string[];
  forbidden_traffic?: string[];
  partner_notes?: string | null;
  attribution_window_days?: number;
  is_own_offer?: boolean;
}

export interface OfferFormValues {
  name: string;
  category: string;
  image_url: string | null;
  description: string;
  conversion_type: string;
  commission_type: string;
  commission_value: string;
  commission_currency: string;
  attribution_window_days: string;
  access_policy: string;
  geo: string;
  allowed_traffic: string[];
  forbidden_traffic: string[];
  partner_notes: string;
  product_url: string;
  restrictions_custom: string;
  selected_restrictions: string[];
}

export const emptyOfferForm = (): OfferFormValues => ({
  name: '',
  category: 'SaaS',
  image_url: null,
  description: '',
  conversion_type: 'sale',
  commission_type: 'percent',
  commission_value: '10',
  commission_currency: 'RUB',
  attribution_window_days: '30',
  access_policy: 'open',
  geo: 'RU',
  allowed_traffic: ['seo', 'content', 'social', 'telegram'],
  forbidden_traffic: [],
  partner_notes: '',
  product_url: '',
  restrictions_custom: '',
  selected_restrictions: [],
});

/** Пустая форма для wizard создания — без предзаполненных значений, влияющих на checklist. */
export const blankOfferForm = (): OfferFormValues => ({
  name: '',
  category: '',
  image_url: null,
  description: '',
  conversion_type: '',
  commission_type: 'percent',
  commission_value: '',
  commission_currency: 'RUB',
  attribution_window_days: '',
  access_policy: 'open',
  geo: '',
  allowed_traffic: [],
  forbidden_traffic: [],
  partner_notes: '',
  product_url: '',
  restrictions_custom: '',
  selected_restrictions: [],
});

import { buildPartnerNotes } from '@/shared/offers/wizard/meta';

export function formToPayload(form: OfferFormValues, status: string) {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    image_url: form.image_url,
    category: form.category || null,
    geo: form.geo || null,
    conversion_type: form.conversion_type,
    commission_type: form.commission_type,
    commission_value: Number(form.commission_value),
    commission_currency: form.commission_currency || 'RUB',
    attribution_window_days: Number(form.attribution_window_days),
    access_policy: form.access_policy,
    visibility: 'public',
    allowed_traffic: form.allowed_traffic,
    forbidden_traffic: form.forbidden_traffic,
    partner_notes: buildPartnerNotes(form),
    product_url: form.product_url.trim() || null,
    status,
  };
}
