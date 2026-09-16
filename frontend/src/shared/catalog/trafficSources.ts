export type TrafficGroup = "CONTENT" | "PAID" | "DIRECT" | "SPECIAL" | "OFFLINE";

export type TrafficSource = {
  code: string;
  nameRu: string;
  nameEn: string;
  group: TrafficGroup;
};

export const TRAFFIC_GROUPS: TrafficGroup[] = [
  "CONTENT",
  "PAID",
  "DIRECT",
  "SPECIAL",
  "OFFLINE",
];

export const TRAFFIC_SOURCES: TrafficSource[] = [
  { code: "WEBSITE_CONTENT", nameRu: "Сайты и блоги", nameEn: "Websites and blogs", group: "CONTENT" },
  { code: "SEO", nameRu: "SEO / поисковый органический трафик", nameEn: "SEO / organic search", group: "CONTENT" },
  { code: "SOCIAL_ORGANIC", nameRu: "Социальные сети", nameEn: "Social networks", group: "CONTENT" },
  { code: "MESSENGERS", nameRu: "Мессенджеры", nameEn: "Messengers", group: "CONTENT" },
  { code: "VIDEO_CONTENT", nameRu: "Видео-контент", nameEn: "Video content", group: "CONTENT" },
  { code: "COMMUNITIES_FORUMS", nameRu: "Форумы и сообщества", nameEn: "Forums and communities", group: "CONTENT" },
  { code: "REVIEWS", nameRu: "Обзоры и рейтинги", nameEn: "Reviews and ratings", group: "CONTENT" },
  { code: "MEDIA_PUBLISHERS", nameRu: "Онлайн-СМИ", nameEn: "Online media", group: "CONTENT" },
  { code: "SEARCH_ADS", nameRu: "Контекстная / поисковая реклама", nameEn: "Search ads", group: "PAID" },
  { code: "SOCIAL_PAID", nameRu: "Таргетированная реклама", nameEn: "Targeted ads", group: "PAID" },
  { code: "DISPLAY_ADS", nameRu: "Баннерная реклама", nameEn: "Display ads", group: "PAID" },
  { code: "NATIVE_ADS", nameRu: "Нативная реклама", nameEn: "Native ads", group: "PAID" },
  { code: "TEASER_ADS", nameRu: "Тизерная реклама", nameEn: "Teaser ads", group: "PAID" },
  { code: "PROGRAMMATIC", nameRu: "Programmatic", nameEn: "Programmatic", group: "PAID" },
  { code: "VIDEO_ADS", nameRu: "Видеореклама", nameEn: "Video ads", group: "PAID" },
  { code: "IN_APP_ADS", nameRu: "Реклама внутри приложений", nameEn: "In-app ads", group: "PAID" },
  { code: "POP_TRAFFIC", nameRu: "Pop / Popunder", nameEn: "Pop / Popunder", group: "PAID" },
  { code: "REDIRECT_TRAFFIC", nameRu: "Redirect-трафик", nameEn: "Redirect traffic", group: "PAID" },
  { code: "INTERSTITIAL_ADS", nameRu: "Interstitial", nameEn: "Interstitial", group: "PAID" },
  { code: "EMAIL", nameRu: "Email", nameEn: "Email", group: "DIRECT" },
  { code: "SMS", nameRu: "SMS", nameEn: "SMS", group: "DIRECT" },
  { code: "WEB_PUSH", nameRu: "Web Push", nameEn: "Web Push", group: "DIRECT" },
  { code: "MOBILE_PUSH", nameRu: "Mobile Push", nameEn: "Mobile Push", group: "DIRECT" },
  { code: "CALL_CENTER", nameRu: "Call-center / телемаркетинг", nameEn: "Call-center / telemarketing", group: "DIRECT" },
  { code: "INFLUENCERS", nameRu: "Блогеры / инфлюенсеры", nameEn: "Bloggers / influencers", group: "SPECIAL" },
  { code: "COMPARISON_SITES", nameRu: "Сайты сравнения", nameEn: "Comparison sites", group: "SPECIAL" },
  { code: "SUB_AFFILIATE", nameRu: "Субпартнёрские сети", nameEn: "Sub-affiliate networks", group: "SPECIAL" },
  { code: "MOBILE_APPS", nameRu: "Мобильные приложения", nameEn: "Mobile apps", group: "SPECIAL" },
  { code: "BROWSER_EXTENSIONS", nameRu: "Расширения браузера", nameEn: "Browser extensions", group: "SPECIAL" },
  { code: "PERSONAL_REFERRAL", nameRu: "Личные рекомендации", nameEn: "Personal referrals", group: "SPECIAL" },
  { code: "OFFLINE_QR", nameRu: "Офлайн / QR", nameEn: "Offline / QR", group: "OFFLINE" },
  { code: "PRINT_MEDIA", nameRu: "Печатные материалы", nameEn: "Print materials", group: "OFFLINE" },
  { code: "OUTDOOR_ADVERTISING", nameRu: "Наружная реклама", nameEn: "Outdoor advertising", group: "OFFLINE" },
  { code: "EVENTS", nameRu: "Мероприятия", nameEn: "Events", group: "OFFLINE" },
  { code: "POS_OFFLINE", nameRu: "Точки продаж", nameEn: "Points of sale", group: "OFFLINE" },
];

export const LEGACY_TRAFFIC_MAP: Record<string, string> = {
  "seo": "SEO",
  "content": "WEBSITE_CONTENT",
  "social": "SOCIAL_ORGANIC",
  "youtube": "VIDEO_CONTENT",
  "telegram": "MESSENGERS",
  "email": "EMAIL",
  "ppc": "SEARCH_ADS",
};

const trafficByCode = new Map(TRAFFIC_SOURCES.map((item) => [item.code, item]));

export function normalizeTrafficSource(code?: string | null): string | null {
  if (code == null) return null;
  const text = String(code).trim();
  if (!text) return null;
  if (trafficByCode.has(text)) return text;
  if (text in LEGACY_TRAFFIC_MAP) return LEGACY_TRAFFIC_MAP[text];
  const upper = text.toUpperCase();
  if (trafficByCode.has(upper)) return upper;
  return LEGACY_TRAFFIC_MAP[text.toLowerCase()] ?? null;
}

export function trafficSourceLabel(code?: string | null): string {
  const normalized = normalizeTrafficSource(code);
  const source = normalized ? trafficByCode.get(normalized) : undefined;
  return source?.nameRu ?? code ?? "";
}

export function searchTrafficSources(query?: string | null): TrafficSource[] {
  const text = (query ?? "").trim().toLowerCase();
  if (!text) return TRAFFIC_SOURCES;
  return TRAFFIC_SOURCES.filter(
    (item) =>
      item.code.toLowerCase().includes(text) ||
      item.nameRu.toLowerCase().includes(text) ||
      item.nameEn.toLowerCase().includes(text) ||
      item.group.toLowerCase().includes(text),
  );
}
