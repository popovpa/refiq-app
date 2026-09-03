import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { dateRangeFromPreset } from './presets';
import {
  dateRangeApiParams,
  dateRangeHasExplicitValue,
  dateRangeSearchParams,
  parseDateRangeSearch,
} from './query';
import { getBrowserTimeZone, parseIsoDate } from './timezone';
import {
  DEFAULT_DATE_RANGE_PRESET,
  type DateRangePreset,
  type DateRangeState,
} from './types';

export function useDateRange(): DateRangeState & {
  setPreset: (preset: DateRangePreset) => void;
  setCustomRange: (from: string, to: string) => void;
  apiParams: Record<string, string>;
} {
  const [searchParams, setSearchParams] = useSearchParams();
  const timezone = useMemo(() => getBrowserTimeZone(), []);
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;

  const range = useMemo(
    () => parseDateRangeSearch(searchParams, timezone),
    [searchParams, timezone],
  );

  useEffect(() => {
    if (dateRangeHasExplicitValue(searchParams)) return;
    const next = dateRangeSearchParams(
      dateRangeFromPreset(DEFAULT_DATE_RANGE_PRESET, timezone),
      searchParams,
    );
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, timezone]);

  const apply = useCallback(
    (state: DateRangeState) => {
      setSearchParams(dateRangeSearchParams(state, searchParamsRef.current), { replace: false });
    },
    [setSearchParams],
  );

  const setPreset = useCallback(
    (preset: DateRangePreset) => {
      apply(dateRangeFromPreset(preset, timezone));
    },
    [apply, timezone],
  );

  const setCustomRange = useCallback(
    (from: string, to: string) => {
      const start = parseIsoDate(from);
      const end = parseIsoDate(to);
      if (!start || !end) return;
      apply(parseDateRangeSearch(new URLSearchParams({ from, to }), timezone));
    },
    [apply, timezone],
  );

  return {
    ...range,
    setPreset,
    setCustomRange,
    apiParams: dateRangeApiParams(range),
  };
}
