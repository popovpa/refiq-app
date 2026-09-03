import { describe, expect, it } from 'vitest';
import { parseDateRangeSearch, serializeDateRange } from './query';
import { resolveCustomRange, resolvePresetRange } from './presets';
import { endOfZonedDay, startOfZonedDay, zonedLocalToUtc } from './timezone';

const MOSCOW = 'Europe/Moscow';
const ZURICH = 'Europe/Zurich';
const NEW_YORK = 'America/New_York';

function iso(date: Date) {
  return date.toISOString();
}

describe('preset bounds in IANA timezones', () => {
  it('computes today from local midnight to now in Europe/Moscow', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const range = resolvePresetRange('today', MOSCOW, now);
    expect(iso(range.dateFrom)).toBe('2026-08-31T21:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-09-01T09:15:00.000Z');
  });

  it('computes yesterday as the previous local calendar day', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const range = resolvePresetRange('yesterday', MOSCOW, now);
    expect(iso(range.dateFrom)).toBe('2026-08-30T21:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-08-31T20:59:59.999Z');
  });

  it('includes today plus previous 6 local days for 7d', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const range = resolvePresetRange('7d', MOSCOW, now);
    expect(iso(range.dateFrom)).toBe('2026-08-25T21:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-09-01T09:15:00.000Z');
  });

  it('includes today plus previous 29 local days for 30d', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const range = resolvePresetRange('30d', MOSCOW, now);
    expect(iso(range.dateFrom)).toBe('2026-08-02T21:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-09-01T09:15:00.000Z');
  });

  it('computes this month from the first local day to now', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const range = resolvePresetRange('this_month', MOSCOW, now);
    expect(iso(range.dateFrom)).toBe('2026-08-31T21:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-09-01T09:15:00.000Z');
  });

  it('computes last month as the full previous local calendar month', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const range = resolvePresetRange('last_month', MOSCOW, now);
    expect(iso(range.dateFrom)).toBe('2026-07-31T21:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-08-31T20:59:59.999Z');
  });

  it('uses calendar dates for a custom range', () => {
    const range = resolveCustomRange(
      { year: 2026, month: 8, day: 1 },
      { year: 2026, month: 8, day: 31 },
      MOSCOW,
    );
    expect(iso(range.dateFrom)).toBe('2026-07-31T21:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-08-31T20:59:59.999Z');
  });
});

describe('DST boundaries', () => {
  it('keeps Zurich spring-forward day as a full local calendar day', () => {
    const start = startOfZonedDay(2026, 3, 29, ZURICH);
    const end = endOfZonedDay(2026, 3, 29, ZURICH);
    expect(iso(start)).toBe('2026-03-28T23:00:00.000Z');
    expect(iso(end)).toBe('2026-03-29T21:59:59.999Z');
    expect(end.getTime() - start.getTime()).toBeLessThan(24 * 60 * 60 * 1000);
  });

  it('keeps Zurich fall-back day as a full local calendar day', () => {
    const start = startOfZonedDay(2026, 10, 25, ZURICH);
    const end = endOfZonedDay(2026, 10, 25, ZURICH);
    expect(iso(start)).toBe('2026-10-24T22:00:00.000Z');
    expect(iso(end)).toBe('2026-10-25T22:59:59.999Z');
    expect(end.getTime() - start.getTime()).toBeGreaterThan(24 * 60 * 60 * 1000);
  });

  it('converts New York spring-forward midnight correctly', () => {
    const start = startOfZonedDay(2026, 3, 8, NEW_YORK);
    expect(iso(start)).toBe('2026-03-08T05:00:00.000Z');
    const afterGap = zonedLocalToUtc(2026, 3, 8, 3, 30, 0, 0, NEW_YORK);
    expect(afterGap.toISOString()).toBe('2026-03-08T07:30:00.000Z');
  });

  it('does not use a fixed UTC offset for 7d across a DST change', () => {
    const now = new Date('2026-03-30T12:00:00.000Z');
    const range = resolvePresetRange('7d', ZURICH, now);
    expect(iso(range.dateFrom)).toBe('2026-03-23T23:00:00.000Z');
    expect(iso(range.dateTo)).toBe('2026-03-30T12:00:00.000Z');
  });
});

describe('query parameters', () => {
  it('restores a preset from period and ignores missing timezone', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const state = parseDateRangeSearch(new URLSearchParams('period=today'), MOSCOW, now);
    expect(state.preset).toBe('today');
    expect(iso(state.dateFrom)).toBe('2026-08-31T21:00:00.000Z');
    expect(serializeDateRange(state)).toEqual({ period: 'today' });
  });

  it('restores a custom range from from/to calendar dates', () => {
    const state = parseDateRangeSearch(new URLSearchParams('from=2026-08-01&to=2026-08-31'), MOSCOW);
    expect(state.preset).toBeUndefined();
    expect(iso(state.dateFrom)).toBe('2026-07-31T21:00:00.000Z');
    expect(iso(state.dateTo)).toBe('2026-08-31T20:59:59.999Z');
    expect(serializeDateRange(state)).toEqual({ from: '2026-08-01', to: '2026-08-31' });
  });

  it('defaults to last 7 days when the URL has no period', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const state = parseDateRangeSearch(new URLSearchParams(), MOSCOW, now);
    expect(state.preset).toBe('7d');
    expect(iso(state.dateFrom)).toBe('2026-08-25T21:00:00.000Z');
  });

  it('does not keep period together with from/to', () => {
    const now = new Date('2026-09-01T09:15:00.000Z');
    const mixed = parseDateRangeSearch(
      new URLSearchParams('period=today&from=2026-08-01&to=2026-08-31'),
      MOSCOW,
      now,
    );
    expect(mixed.preset).toBe('7d');
    expect(serializeDateRange(mixed)).toEqual({ period: '7d' });
  });
});
