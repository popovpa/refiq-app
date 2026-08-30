export type CreativeType = 'text' | 'social_post' | 'banner';
export type CreativeStatus = 'draft' | 'active' | 'archived';
export type CreativeSource = 'business' | 'partner' | 'ai';
export type BannerFormat = 'square_1_1' | 'portrait_4_5' | 'landscape_16_9' | 'story_9_16';

export interface CreativePolicyIssue {
  code: string;
  severity: 'warning' | 'blocked';
  message: string;
}

export interface Creative {
  id: number;
  offer_id: number;
  partner_id: number | null;
  type: CreativeType;
  source: CreativeSource;
  status: CreativeStatus;
  title: string | null;
  headline: string | null;
  body: string | null;
  cta: string | null;
  hashtags: string[];
  items?: string[];
  descriptions?: string[];
  primary_texts?: string[];
  hooks?: string[];
  captions?: string[];
  ctas?: string[];
  variants?: CreativeTextVariant[];
  asset_id: number | null;
  asset?: { url?: string | null; mime_type?: string; width?: number; height?: number } | null;
  language: string | null;
  channel: string | null;
  format: string | null;
  generation_id: string | null;
  selected_variant?: string | null;
  policy_status: string | null;
  policy_issues: CreativePolicyIssue[];
  updated_at?: string | null;
}

export interface CreativeTextVariant {
  headline?: string | null;
  body?: string | null;
  cta?: string | null;
  hashtags?: string[];
}

export interface CreativeVariant {
  kind?: string;
  headline?: string;
  body?: string;
  cta?: string;
  hashtags?: string[];
  asset_id?: number;
  width?: number;
  height?: number;
  mime_type?: string;
  format?: string;
  policy?: { status: string; issues: CreativePolicyIssue[] };
}

export interface GenerationResponse {
  generation_id: string;
  status: 'processing' | 'completed' | 'failed';
  variants?: CreativeVariant[];
  proposed?: CreativeVariant;
  created_ids?: number[];
  errors?: { slot?: string; code?: string }[];
  policy?: { status: string; issues: CreativePolicyIssue[] };
  error?: { code?: string; message?: string };
}

export type PromoGenerationRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'completed_with_errors'
  | 'cancel_requested'
  | 'cancelled'
  | 'failed';

export type PromoGenerationItemStatus = 'queued' | 'generating' | 'completed' | 'failed' | 'cancelled';

export interface PromoGenerationItem {
  id: number;
  generation_run_id: number;
  material_type: string;
  channel: string | null;
  label: string;
  group: string;
  status: PromoGenerationItemStatus;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  promo_material_id: number | null;
  material_ids: number[];
}

export interface PromoGenerationRun {
  id: number;
  run_id: number;
  generation_id: string;
  offer_id: number;
  status: PromoGenerationRunStatus;
  total_items: number;
  completed_items: number;
  failed_items: number;
  cancelled_items: number;
  processed_items: number;
  percentage: number;
  cancel_requested: boolean;
  items: PromoGenerationItem[];
  created_ids: number[];
  errors: { item_id?: number; slot?: string; code?: string; message?: string }[];
}

export interface PromoCatalogItem {
  id: string;
  group: string;
  label: string;
  recommended: boolean;
}
