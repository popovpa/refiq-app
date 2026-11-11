import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Chart, Credits } from '@highcharts/react';
import type Highcharts from 'highcharts';
import { mergeRefiqOptions } from './theme';

function useReducedMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const apply = () => setReduce(media.matches);
    apply();
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, []);
  return reduce;
}

export function RefiqChart({
  options,
  height = 288,
  children,
}: {
  options: Highcharts.Options;
  height?: number;
  children?: ReactNode;
}) {
  const reduceMotion = useReducedMotion();
  const merged = useMemo(
    () => mergeRefiqOptions(options, height, reduceMotion),
    [options, height, reduceMotion],
  );
  return (
    <Chart options={merged} containerProps={{ style: { width: '100%', height, minWidth: 0 } }}>
      <Credits enabled={false} />
      {children}
    </Chart>
  );
}
