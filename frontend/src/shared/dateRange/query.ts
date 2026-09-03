import { dateRangeFromPreset, isDateRangePreset, resolveCustomRange } from './presets';
import {
  calendarDateFromInstant,
  parseIsoDate,
  toIsoDate,
} from './timezone';
import { DEFAULT_DATE_RANGE_PRESET, type DateRangePreset, type DateRangeState } from './types';

export type DateRangeSearch = {
  get: (name: string) => string | null;
};

export type DateRangeQuery = {
  period?: DateRangePreset;
  from?: string;
  to?: string;
};

export function parseDateRangeSearch(
  search: DateRangeSearch,
  timeZone: string,
  now: Date = new Date(),
): DateRangeState {
  const period = search.get('period');
  const from = search.get('from');
  const to = search.get('to');

  if (from && to && !period) {
    const start = parseIsoDate(from);
    const end = parseIsoDate(to);
    if (start && end) {
      return {
        timezone: timeZone,
        ...resolveCustomRange(start, end, timeZone),
      };
    }
  }

  if (isDateRangePreset(period) && !from && !to) {
    return dateRangeFromPreset(period, timeZone, now);
  }

  return dateRangeFromPreset(DEFAULT_DATE_RANGE_PRESET, timeZone, now);
}

export function serializeDateRange(state: DateRangeState): DateRangeQuery {
  if (state.preset) {
    return { period: state.preset };
  }
  const from = calendarDateFromInstant(state.dateFrom, state.timezone);
  const to = calendarDateFromInstant(state.dateTo, state.timezone);
  return {
    from: toIsoDate(from.year, from.month, from.day),
    to: toIsoDate(to.year, to.month, to.day),
  };
}

export function dateRangeSearchParams(state: DateRangeState, current: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(current);
  next.delete('period');
  next.delete('from');
  next.delete('to');
  const serialized = serializeDateRange(state);
  if (serialized.period) {
    next.set('period', serialized.period);
  } else if (serialized.from && serialized.to) {
    next.set('from', serialized.from);
    next.set('to', serialized.to);
  }
  return next;
}

export function dateRangeHasExplicitValue(search: DateRangeSearch): boolean {
  const period = search.get('period');
  const from = search.get('from');
  const to = search.get('to');
  if (isDateRangePreset(period) && !from && !to) return true;
  if (from && to && !period && parseIsoDate(from) && parseIsoDate(to)) return true;
  return false;
}

export function dateRangeApiParams(state: DateRangeState): Record<string, string> {
  return {
    from: state.dateFrom.toISOString(),
    to: state.dateTo.toISOString(),
    timezone: state.timezone,
  };
}

export function withDateRangeQuery(path: string, state: DateRangeState): string {
  const params = new URLSearchParams(dateRangeApiParams(state));
  const [base, existing] = path.split('?');
  if (existing) {
    const merged = new URLSearchParams(existing);
    for (const [key, value] of params) merged.set(key, value);
    const qs = merged.toString();
    return qs ? `${base}?${qs}` : base;
  }
  return `${base}?${params.toString()}`;
}
