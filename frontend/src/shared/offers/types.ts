import { parseGeoCodes } from '@/shared/catalog/countries';
import { normalizeTrafficSource } from '@/shared/catalog/trafficSources';
import { resolveCategoryCode } from '@/shared/catalog/categories';

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
  category_id?: number | null;
  category_code?: string | null;
  category_name?: string | null;
  vertical_code?: string | null;
  vertical_name?: string | null;
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
  rejection_reason?: string | null;
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
  hold_period_days?: number;
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
  hold_period_days: string;
  access_policy: string;
  geo_countries: string[];
  allowed_traffic: string[];
  partner_notes: string;
  product_url: string;
}

export const emptyOfferForm = (): OfferFormValues => ({
  name: '',
  category: '',
  image_url: null,
  description: '',
  conversion_type: 'sale',
  commission_type: 'percent',
  commission_value: '10',
  commission_currency: 'RUB',
  attribution_window_days: '30',
  hold_period_days: '0',
  access_policy: 'approval',
  geo_countries: [],
  allowed_traffic: [],
  partner_notes: '',
  product_url: '',
});

export const blankOfferForm = (): OfferFormValues => ({
  name: '',
  category: '',
  image_url: null,
  description: '',
  conversion_type: 'sale',
  commission_type: 'percent',
  commission_value: '',
  commission_currency: 'RUB',
  attribution_window_days: '30',
  hold_period_days: '0',
  access_policy: 'approval',
  geo_countries: [],
  allowed_traffic: [],
  partner_notes: '',
  product_url: '',
});

export function formToPayload(form: OfferFormValues, status: string) {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    image_url: form.image_url,
    category: form.category || null,
    geo: form.geo_countries,
    conversion_type: form.conversion_type,
    commission_type: form.commission_type,
    commission_value: Number(form.commission_value),
    commission_currency: form.commission_currency || 'RUB',
    attribution_window_days: Number(form.attribution_window_days),
    hold_period_days: Number(form.hold_period_days),
    access_policy: form.access_policy,
    visibility: 'public',
    allowed_traffic: form.allowed_traffic,
    partner_notes: form.partner_notes.trim() || null,
    product_url: form.product_url.trim() || null,
    status,
  };
}

export function offerToForm(data: {
  name: string;
  description?: string | null;
  image_url?: string | null;
  category?: string | null;
  category_code?: string | null;
  geo?: string | string[] | null;
  conversion_type?: string;
  access_policy?: string;
  attribution_window_days?: number;
  hold_period_days?: number;
  partner_notes?: string | null;
  allowed_traffic?: string[];
  product_url?: string | null;
  commission_rules?: Array<{ type: string; value: number; currency: string | null }>;
}): OfferFormValues {
  const rule = data.commission_rules?.[0];
  return {
    name: data.name || '',
    category: resolveCategoryCode(data.category_code || data.category) || '',
    image_url: data.image_url || null,
    description: data.description || '',
    conversion_type: data.conversion_type || 'sale',
    commission_type: rule?.type || 'percent',
    commission_value: String(rule?.value ?? ''),
    commission_currency: rule?.currency || 'RUB',
    attribution_window_days: String(data.attribution_window_days || 30),
    hold_period_days: String(data.hold_period_days ?? 0),
    access_policy: data.access_policy || 'approval',
    geo_countries: parseGeoCodes(data.geo),
    allowed_traffic: (data.allowed_traffic || [])
      .map((item) => normalizeTrafficSource(item))
      .filter((item): item is string => Boolean(item)),
    partner_notes: data.partner_notes || '',
    product_url: data.product_url || '',
  };
}
