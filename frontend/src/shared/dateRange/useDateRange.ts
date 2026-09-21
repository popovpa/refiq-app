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
  const searchKey = searchParams.toString();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const nowRef = useRef(new Date());

  const range = useMemo(
    () => parseDateRangeSearch(new URLSearchParams(searchKey), timezone, nowRef.current),
    [searchKey, timezone],
  );

  useEffect(() => {
    const params = new URLSearchParams(searchKey);
    if (dateRangeHasExplicitValue(params)) return;
    const next = dateRangeSearchParams(
      dateRangeFromPreset(DEFAULT_DATE_RANGE_PRESET, timezone, nowRef.current),
      params,
    );
    setSearchParams(next, { replace: true });
  }, [searchKey, setSearchParams, timezone]);

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

  const apiParams = useMemo(() => dateRangeApiParams(range), [range]);

  return {
    ...range,
    setPreset,
    setCustomRange,
    apiParams,
  };
}
