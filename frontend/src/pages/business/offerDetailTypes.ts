import type { BusinessPromotionLink } from '@/shared/links/BusinessLinkDetailDrawer';

export interface OfferPartnerRow {
  id: number;
  partner_id: number;
  name: string;
  email: string;
  status: string;
  source: string;
  comment?: string | null;
  traffic_sources?: string[];
  topics?: string | null;
  geo?: string | null;
  clicks: number;
  conversions: number;
  cr: number;
  commissions: number;
  revenue?: number;
}

export interface TrafficSplitStats {
  clicks: number;
  conversions: number;
  cr: number;
  revenue: number;
  commissions: number;
}

export interface TrafficSplit {
  own: TrafficSplitStats;
  partner: TrafficSplitStats;
}

export interface BusinessOfferDetailData {
  id: number;
  name: string;
  description: string | null;
  image_url?: string | null;
  category?: string | null;
  geo?: string | null;
  status: string;
  access_policy: string;
  conversion_type: string;
  attribution_window_days: number;
  attribution_model?: string;
  currency: string;
  allowed_traffic?: string[];
  forbidden_traffic?: string[];
  partner_notes?: string | null;
  commission_rules: Array<{ type: string; value: number; currency: string | null }>;
  kpis: {
    clicks: number;
    conversions: number;
    cr: number;
    revenue: number;
    commissions: number;
    approved_conversions?: number;
  };
  timeseries: Array<{ date: string; clicks: number; conversions: number }>;
  partners: OfferPartnerRow[];
  pending_applications: OfferPartnerRow[];
  top_partners: OfferPartnerRow[];
  active_partners: number;
  active_links: number;
  promotion_links: BusinessPromotionLink[];
  traffic_split?: TrafficSplit;
  warnings: string[];
}
