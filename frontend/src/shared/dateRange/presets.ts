import {
  DATE_RANGE_PRESETS,
  DEFAULT_DATE_RANGE_PRESET,
  type DateRangePreset,
  type DateRangeState,
} from './types';
import {
  addCalendarDays,
  calendarDateFromInstant,
  endOfZonedDay,
  startOfZonedDay,
} from './timezone';

export function isDateRangePreset(value: string | null | undefined): value is DateRangePreset {
  return DATE_RANGE_PRESETS.includes(value as DateRangePreset);
}

export function resolvePresetRange(
  preset: DateRangePreset,
  timeZone: string,
  now: Date = new Date(),
): { dateFrom: Date; dateTo: Date } {
  const today = calendarDateFromInstant(now, timeZone);

  if (preset === 'today') {
    return {
      dateFrom: startOfZonedDay(today.year, today.month, today.day, timeZone),
      dateTo: now,
    };
  }

  if (preset === 'yesterday') {
    const day = addCalendarDays(today.year, today.month, today.day, -1);
    return {
      dateFrom: startOfZonedDay(day.year, day.month, day.day, timeZone),
      dateTo: endOfZonedDay(day.year, day.month, day.day, timeZone),
    };
  }

  if (preset === '7d' || preset === '30d') {
    const back = preset === '7d' ? 6 : 29;
    const start = addCalendarDays(today.year, today.month, today.day, -back);
    return {
      dateFrom: startOfZonedDay(start.year, start.month, start.day, timeZone),
      dateTo: now,
    };
  }

  if (preset === 'this_month') {
    return {
      dateFrom: startOfZonedDay(today.year, today.month, 1, timeZone),
      dateTo: now,
    };
  }

  const prevMonth = addCalendarDays(today.year, today.month, 1, -1);
  const lastMonthStart = { year: prevMonth.year, month: prevMonth.month, day: 1 };
  return {
    dateFrom: startOfZonedDay(lastMonthStart.year, lastMonthStart.month, 1, timeZone),
    dateTo: endOfZonedDay(prevMonth.year, prevMonth.month, prevMonth.day, timeZone),
  };
}

export function resolveCustomRange(
  from: { year: number; month: number; day: number },
  to: { year: number; month: number; day: number },
  timeZone: string,
): { dateFrom: Date; dateTo: Date } {
  let start = from;
  let end = to;
  const startUtc = startOfZonedDay(from.year, from.month, from.day, timeZone);
  const endUtc = endOfZonedDay(to.year, to.month, to.day, timeZone);
  if (startUtc.getTime() > endUtc.getTime()) {
    start = to;
    end = from;
  }
  return {
    dateFrom: startOfZonedDay(start.year, start.month, start.day, timeZone),
    dateTo: endOfZonedDay(end.year, end.month, end.day, timeZone),
  };
}

export function dateRangeFromPreset(
  preset: DateRangePreset = DEFAULT_DATE_RANGE_PRESET,
  timeZone: string,
  now?: Date,
): DateRangeState {
  const bounds = resolvePresetRange(preset, timeZone, now);
  return {
    preset,
    timezone: timeZone,
    ...bounds,
  };
}
