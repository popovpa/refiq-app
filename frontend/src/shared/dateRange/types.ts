export const DATE_RANGE_FILTER_MODES = ['header', 'local', 'none'] as const;
export type DateRangeFilterMode = (typeof DATE_RANGE_FILTER_MODES)[number];

export const DATE_RANGE_PRESETS = [
  'today',
  'yesterday',
  '7d',
  '30d',
  'this_month',
  'last_month',
] as const;

export type DateRangePreset = (typeof DATE_RANGE_PRESETS)[number];

export type DateRangeState = {
  preset?: DateRangePreset;
  dateFrom: Date;
  dateTo: Date;
  timezone: string;
};

export const DEFAULT_DATE_RANGE_PRESET: DateRangePreset = '7d';

export const DATE_RANGE_PRESET_LABELS: Record<DateRangePreset, string> = {
  today: 'Сегодня',
  yesterday: 'Вчера',
  '7d': 'Последние 7 дней',
  '30d': 'Последние 30 дней',
  this_month: 'Этот месяц',
  last_month: 'Прошлый месяц',
};

export const CUSTOM_RANGE_LABEL = 'Произвольный интервал';
