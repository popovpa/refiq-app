export type SettingsTab = 'company' | 'legal' | 'sites' | 'integrations' | 'defaults';
export type IntegrationKind = 'postback' | 'sdk';

export interface BusinessWorkspaceSettings {
  id: number | string;
  name: string;
  legal_name?: string | null;
  country: string | null;
  currency: string;
  website: string;
  category: string;
  work_email: string;
  phone: string;
  description: string;
  logo_url: string | null;
  default_attribution_window_days: number;
  default_access_policy: string;
  default_confirmation_days: number;
}

export type CompanyForm = {
  name: string;
  website: string;
  country: string;
  category: string;
  work_email: string;
  phone: string;
  description: string;
  logo_url: string | null;
};

export type DefaultsForm = {
  currency: string;
  default_attribution_window_days: string;
  default_access_policy: string;
  default_confirmation_days: string;
};

export const POSTBACK_ENDPOINT = 'https://api.refiq.ru/postback';
export const POSTBACK_AUTH_EXAMPLE = 'Bearer <POSTBACK_TOKEN>';

export type PostbackIntegrationStatus = 'not_configured' | 'awaiting_first_request' | 'connected';

export interface PostbackCredentialStatus {
  configured: boolean;
  token_suffix?: string | null;
  created_at?: string | null;
  last_success_at?: string | null;
  token_status?: string | null;
  integration_status: PostbackIntegrationStatus;
}

export interface PostbackTokenCreated {
  token: string;
  token_suffix: string;
  created_at: string;
}

export function maskPostbackToken(suffix?: string | null) {
  if (!suffix) return '';
  return `rqpb_${'•'.repeat(20)}${suffix}`;
}

export function postbackStatusLabel(status?: PostbackIntegrationStatus | null) {
  if (status === 'connected') return 'Подключено';
  if (status === 'awaiting_first_request') return 'Ожидает первого запроса';
  return 'Не настроено';
}

export function postbackStatusClass(status?: PostbackIntegrationStatus | null) {
  if (status === 'connected') return 'bg-success/10 text-success';
  if (status === 'awaiting_first_request') return 'bg-yellow-50 text-yellow-700';
  return 'bg-muted text-muted-foreground';
}

export function postbackCurlExample() {
  return `curl -X POST ${POSTBACK_ENDPOINT} \\
  -H "Authorization: Bearer $REFIQ_POSTBACK_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "rqcid": "a1b2c3d4e5f6"
  }'`;
}

export function formatPostbackDate(value?: string | null, withTime = false) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return withTime
    ? date.toLocaleString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function toCompanyForm(data: BusinessWorkspaceSettings): CompanyForm {
  return {
    name: data.name || '',
    website: data.website || '',
    country: data.country || '',
    category: data.category || '',
    work_email: data.work_email || '',
    phone: data.phone || '',
    description: data.description || '',
    logo_url: data.logo_url || null,
  };
}

export function toDefaultsForm(data: BusinessWorkspaceSettings): DefaultsForm {
  return {
    currency: data.currency || 'RUB',
    default_attribution_window_days: String(data.default_attribution_window_days || 30),
    default_access_policy: data.default_access_policy || 'approval',
    default_confirmation_days: String(data.default_confirmation_days ?? 30),
  };
}

export function websiteHost(url?: string | null) {
  if (!url?.trim()) return '';
  try {
    const withProtocol = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    return new URL(withProtocol).hostname.replace(/^www\./, '');
  } catch {
    return url.replace(/^https?:\/\//i, '').replace(/\/.*$/, '');
  }
}

export type SdkIntegrationStatus = PostbackIntegrationStatus;

export interface SdkCredentialStatus {
  configured: boolean;
  script_id?: string | null;
  created_at?: string | null;
  last_success_at?: string | null;
  integration_status: SdkIntegrationStatus;
  sites_count?: number;
  connected_sites?: number;
}

export interface SdkCredentialCreated {
  script_id: string;
  created_at: string;
}

export type SiteDisplayStatus = 'connected' | 'needs_setup' | 'disabled';
export type SiteSdkStatus = 'connected' | 'not_detected';

export interface BusinessSite {
  id: number;
  business_id: number;
  name: string;
  domain: string;
  status: 'active' | 'disabled';
  display_status: SiteDisplayStatus;
  site_key: string;
  sdk_status: SiteSdkStatus;
  last_success_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  disabled_at?: string | null;
  can_delete: boolean;
}

export function siteStatusLabel(status?: SiteDisplayStatus | null) {
  if (status === 'connected') return 'Подключен';
  if (status === 'needs_setup') return 'Требует настройки';
  if (status === 'disabled') return 'Отключен';
  return 'Требует настройки';
}

export function siteStatusClass(status?: SiteDisplayStatus | null) {
  if (status === 'connected') return 'bg-success/10 text-success';
  if (status === 'needs_setup') return 'bg-yellow-50 text-yellow-700';
  return 'bg-muted text-muted-foreground';
}

export function siteSdkLabel(status?: SiteSdkStatus | null) {
  return status === 'connected' ? 'SDK работает' : 'SDK ещё не обнаружен';
}

export function sdkStatusLabel(status?: SdkIntegrationStatus | null) {
  if (status === 'connected') return 'Подключено';
  if (status === 'awaiting_first_request') return 'Ожидает первого запроса';
  return 'Не подключено';
}

export function sdkSnippet(siteKey: string) {
  return `<script>
  (function (window) {
    var match = location.href.match(/[?&#]rqcid=([a-z0-9]{12})/);
    if (match) {
      document.cookie = "rqcid=" + match[1] + ";path=/;max-age=31536000;SameSite=Lax";
    }
    var queue = (window.RefIQ = window.RefIQ || []);
    queue.event = function (name, data) {
      queue.push(["event", name, data]);
    };
  })(window);
</script>
<script async src="https://refiq.ru/sdk.js" data-site-id="${siteKey}"></script>`;
}
