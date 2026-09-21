export const ONBOARDING_COUNTRIES = [
  { value: 'RU', label: 'Россия' },
  { value: 'KZ', label: 'Казахстан' },
  { value: 'BY', label: 'Беларусь' },
  { value: 'UA', label: 'Украина' },
  { value: 'US', label: 'Соединённые Штаты' },
  { value: 'GB', label: 'Великобритания' },
  { value: 'DE', label: 'Германия' },
  { value: 'TR', label: 'Турция' },
];

export const BUSINESS_CATEGORIES = [
  'SaaS',
  'Fintech',
  'Education',
  'E-commerce',
  'Marketing',
  'Услуги',
  'Other',
];

export const PARTNER_ONBOARDING_TYPES = [
  { value: 'INDIVIDUAL', label: 'Самозанятый' },
  { value: 'SOLE_PROPRIETOR', label: 'ИП' },
  { value: 'LEGAL_ENTITY', label: 'Юридическое лицо' },
] as const;

export const BUSINESS_ORG_TYPES = [
  { value: 'SOLE_PROPRIETOR', label: 'ИП' },
  { value: 'LEGAL_ENTITY', label: 'Юридическое лицо' },
] as const;

export type PartnerOnboardingType = (typeof PARTNER_ONBOARDING_TYPES)[number]['value'];
